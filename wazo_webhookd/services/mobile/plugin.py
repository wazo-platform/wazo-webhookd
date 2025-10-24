# Copyright 2017-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from __future__ import annotations

import json
import logging
import tempfile
import warnings
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal, TypedDict, cast

import httpx
from celery import Task
from requests.exceptions import HTTPError
from wazo_auth_client import Client as AuthClient

from wazo_webhookd.plugins.subscription.notifier import SubscriptionNotifier
from wazo_webhookd.plugins.subscription.service import SubscriptionService
from wazo_webhookd.services.helpers import (
    HookExpectedError,
    HookRetry,
    RequestDetailsDict,
    requests_automatic_detail,
    requests_automatic_hook_retry,
)

from ...database.models import Subscription
from .exceptions import NotificationError
from .fcm_client import (
    FCMNotification,
    FCMNotificationLegacy,
    FCMNotificationProtocol,
    RetryAfterException,
)

if TYPE_CHECKING:
    from wazo_auth_client.types import TokenDict

    from ...types import ServicePluginDependencyDict, WebhookdConfigDict

logger = logging.getLogger(__name__)


class ExternalMobileDict(TypedDict):
    token: str
    apns_token: str
    apns_voip_token: str
    apns_notification_token: str


class ExternalConfigDict(TypedDict):
    client_id: str
    client_secret: str
    fcm_api_key: str
    fcm_service_account_info: str
    ios_apn_certificate: str
    ios_apn_private: str
    use_sandbox: bool


EMPTY_EXTERNAL_CONFIG: ExternalConfigDict = {
    'client_id': '',
    'client_secret': '',
    'fcm_api_key': '',
    'fcm_service_account_info': '',
    'ios_apn_certificate': '',
    'ios_apn_private': '',
    'use_sandbox': False,
}


class BaseNotificationPayload(TypedDict):
    notification_type: str
    items: dict[str, Any]


class NotificationPayload(BaseNotificationPayload, total=False):
    pass


ApsContentDict = TypedDict(
    'ApsContentDict',
    {
        'badge': int,
        'sound': str,
        'content-available': int,
        'alert': dict[str, str],
    },
)


class ApnsPayload(BaseNotificationPayload):
    aps: ApsContentDict


ApnsHeaders = TypedDict(
    'ApnsHeaders',
    {
        'apns-topic': str,
        'apns-push-type': str,
        'apns-priority': int,
    },
)


class FcmResponseDict(TypedDict):
    multicast_ids: list
    success: int
    failure: int
    canonical_ids: int
    results: list
    topic_message_id: str | None


class NotificationSentStatusDict(TypedDict):
    success: bool
    protocol_used: Literal['apns', 'fcm']
    full_response: FcmResponseDict | RequestDetailsDict


REQUEST_TIMEOUTS = httpx.Timeout(connect=10, read=15, write=15, pool=None)

DEFAULT_ANDROID_CHANNEL_ID = 'io.wazo.songbird'


class NotificationType(StrEnum):
    MESSAGE_RECEIVED = 'messageReceived'
    VOICEMAIL_RECEIVED = 'voicemailReceived'
    INCOMING_CALL = 'incomingCall'
    CANCEL_INCOMING_CALL = 'cancelIncomingCall'
    PLUGIN = 'plugin'
    MISSED_CALL = 'missedCall'


RESERVED_NOTIFICATION_TYPES = (
    NotificationType.MESSAGE_RECEIVED,
    NotificationType.VOICEMAIL_RECEIVED,
    NotificationType.INCOMING_CALL,
    NotificationType.CANCEL_INCOMING_CALL,
    NotificationType.MISSED_CALL,
)

MAP_NAME_TO_NOTIFICATION_TYPE = {
    'user_voicemail_message_created': NotificationType.VOICEMAIL_RECEIVED,
    'global_voicemail_message_created': NotificationType.VOICEMAIL_RECEIVED,
    'call_push_notification': NotificationType.INCOMING_CALL,
    'call_cancel_push_notification': NotificationType.CANCEL_INCOMING_CALL,
    'chatd_user_room_message_created': NotificationType.MESSAGE_RECEIVED,
    'user_missed_call': NotificationType.MISSED_CALL,
}


class Service:
    subscription_service: SubscriptionService
    _config: WebhookdConfigDict

    def load(self, dependencies: ServicePluginDependencyDict) -> None:
        bus_consumer = dependencies['bus_consumer']
        bus_publisher = dependencies['bus_publisher']
        self._config = dependencies['config']
        self.subscription_service = SubscriptionService(
            self._config, SubscriptionNotifier(bus_publisher)
        )
        bus_consumer.subscribe(
            'auth_user_external_auth_added',
            self.on_external_auth_added,
            headers={'x-internal': True},
        )
        bus_consumer.subscribe(
            'auth_user_external_auth_updated',
            self.on_external_auth_updated,
            headers={'x-internal': True},
        )
        bus_consumer.subscribe(
            'auth_user_external_auth_deleted',
            self.on_external_auth_deleted,
            headers={'x-internal': True},
        )
        logger.info('Mobile push notification plugin is started')

    def on_external_auth_added(self, body: dict, headers: dict):
        if body['data'].get('external_auth_name') == 'mobile':
            user_uuid = body['data']['user_uuid']
            tenant_uuid = headers['tenant_uuid']

            self._ensure_mobile_subscription(user_uuid, tenant_uuid)
            logger.info(
                'User mobile subscription registered: %s/%s', tenant_uuid, user_uuid
            )

    def on_external_auth_updated(self, body, headers):
        if body['data'].get('external_auth_name') == 'mobile':
            user_uuid = body['data']['user_uuid']
            tenant_uuid = headers['tenant_uuid']

            self._ensure_mobile_subscription(user_uuid, tenant_uuid)
            logger.info(
                'User mobile subscription updated: %s/%s', tenant_uuid, user_uuid
            )

    def on_external_auth_deleted(
        self, body: dict[str, Any], headers: dict[str, Any]
    ) -> None:
        if body['data'].get('external_auth_name') == 'mobile':
            user_uuid = body['data']['user_uuid']
            tenant_uuid = headers['tenant_uuid']
            subscriptions = self.subscription_service.list(
                owner_user_uuid=user_uuid,
                owner_tenant_uuids=[tenant_uuid],
                search_metadata={'mobile': 'true'},
            )
            logger.debug(
                'Found %d mobile subscriptions for user %s/%s',
                len(subscriptions),
                tenant_uuid,
                user_uuid,
            )
            for subscription in subscriptions:
                self.subscription_service.delete(subscription.uuid)
            logger.info('User unregistered: %s/%s', tenant_uuid, user_uuid)

    def _ensure_mobile_subscription(self, user_uuid: str, tenant_uuid: str) -> None:
        """Create or update mobile subscription for a user, ensuring only one exists."""
        # Delete any existing mobile subscriptions for this user
        subscriptions = self.subscription_service.list(
            owner_user_uuid=user_uuid,
            owner_tenant_uuids=[tenant_uuid],
            search_metadata={'mobile': 'true'},
        )
        if len(subscriptions) == 1:
            logger.debug(
                'Mobile subscription (uuid=%s) already exists for user (tenant=%s/uuid=%s)',
                subscriptions[0].uuid,
                tenant_uuid,
                user_uuid,
            )
            return

        if len(subscriptions) > 1:
            logger.warning(
                '%d mobile subscriptions found for user %s/%s, cleaning up and keeping only one',
                len(subscriptions),
                tenant_uuid,
                user_uuid,
            )
            for subscription in subscriptions[1:]:
                self.subscription_service.delete(subscription.uuid)
            logger.debug(
                'Mobile subscription (uuid=%s) already exists for user (tenant=%s/uuid=%s)',
                subscriptions[0].uuid,
                tenant_uuid,
                user_uuid,
            )
            return
        if len(subscriptions) == 0:
            logger.info(
                'Creating new mobile subscription for user (tenant=%s/uuid=%s)',
                tenant_uuid,
                user_uuid,
            )
            # Create a new mobile subscription
            self.subscription_service.create(
                {
                    'name': (
                        'Push notification mobile for user '
                        f'{tenant_uuid}/{user_uuid}'
                    ),
                    'service': 'mobile',
                    'events': [
                        'chatd_user_room_message_created',
                        'call_push_notification',
                        'call_cancel_push_notification',
                        'user_voicemail_message_created',
                        'global_voicemail_message_created',
                        'user_missed_call',
                    ],
                    'events_user_uuid': user_uuid,
                    # 'events_tenant_uuid': tenant_uuid,
                    'owner_user_uuid': user_uuid,
                    'owner_tenant_uuid': tenant_uuid,
                    'config': {},
                    'metadata_': {'mobile': 'true'},
                }
            )
            return

    def get_tenant_uuid(self, user_uuid: str) -> str:
        auth, jwt = self.get_auth(self._config)
        return auth.users.get(user_uuid)["tenant_uuid"]

    @classmethod
    def get_auth(cls, config: WebhookdConfigDict) -> tuple[AuthClient, str]:
        auth_config = dict(config['auth'])
        # FIXME(sileht): Keep the certificate
        auth_config['verify_certificate'] = False
        auth = AuthClient(**auth_config)
        token: TokenDict = auth.token.new('wazo_user', expiration=3600)
        auth.set_token(token["token"])
        jwt = token.get("metadata", {}).get("jwt", "")
        auth.username = None
        auth.password = None
        return auth, jwt

    @classmethod
    def get_external_data(
        cls, config: WebhookdConfigDict, user_uuid: str
    ) -> tuple[ExternalMobileDict, ExternalConfigDict, str]:
        auth, jwt = cls.get_auth(config)
        external_tokens: ExternalMobileDict = auth.external.get('mobile', user_uuid)
        tenant_uuid = auth.users.get(user_uuid)['tenant_uuid']
        try:
            external_config: ExternalConfigDict = auth.external.get_config(
                'mobile', tenant_uuid
            )
        except HTTPError as e:
            if e.response and e.response.status_code != 404:
                raise
            external_config = EMPTY_EXTERNAL_CONFIG

        return external_tokens, external_config, jwt

    @classmethod
    def run(
        cls, task: Task, config: WebhookdConfigDict, subscription: Subscription, event
    ) -> FcmResponseDict | RequestDetailsDict | None:
        if not (user_uuid := subscription['events_user_uuid']):
            raise HookExpectedError("subscription doesn't have events_user_uuid set")

        # TODO(sileht): We should also filter on tenant_uuid
        # tenant_uuid = subscription.get('events_tenant_uuid')
        if (
            event['data'].get('user_uuid') == user_uuid
            # and event['data']['tenant_uuid'] == tenant_uuid
            and event['name'] == 'chatd_user_room_message_created'
        ):
            return None

        external_tokens, external_config, jwt = cls.get_external_data(config, user_uuid)
        push = PushNotification(task, config, external_tokens, external_config, jwt)

        data = event.get('data')
        name = event.get('name')

        logger.debug('received event type %s with payload: %s', name, data)
        if notification_type := MAP_NAME_TO_NOTIFICATION_TYPE.get(name):
            logger.debug(
                'notification_type %s identified from event %s', notification_type, name
            )
            return getattr(push, notification_type)(data)

        logger.error('No matching notification type for event %s', name)
        return None


def generate_timestamp() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class PushNotification:
    def __init__(
        self,
        task: Task,
        config: WebhookdConfigDict,
        external_tokens: ExternalMobileDict,
        external_config: ExternalConfigDict,
        jwt: str,
    ) -> None:
        self.task = task
        self.config = config
        self.external_tokens = external_tokens
        self.external_config = external_config
        self.jwt = jwt

    def cancelIncomingCall(self, data: dict[str, Any]) -> NotificationSentStatusDict:
        payload = data | {'notification_timestamp': generate_timestamp()}
        return self.send_notification(
            NotificationType.CANCEL_INCOMING_CALL,
            extra={'items': payload},
            data_only=True,
        )

    def incomingCall(self, data: dict[str, Any]) -> NotificationSentStatusDict:
        payload = data | {'notification_timestamp': generate_timestamp()}
        return self.send_notification(
            NotificationType.INCOMING_CALL,
            'Incoming Call',
            f'From: {payload["peer_caller_id_number"]}',
            {'items': payload},
        )

    def voicemailReceived(self, data: dict[str, Any]) -> NotificationSentStatusDict:
        payload = data | {'notification_timestamp': generate_timestamp()}
        
        # iOS needs alert for killed state, Android works fine with data-only
        if self._can_send_to_apn(self.external_tokens):
            # iOS device - send hybrid notification (alert + content-available)
            message = payload.get('message', {})
            caller_name = message.get('caller_id_name', 'Unknown')
            caller_number = message.get('caller_id_number', '')
            
            return self.send_notification(
                NotificationType.VOICEMAIL_RECEIVED,
                message_title='New Voicemail',
                message_body=f'From: {caller_name} ({caller_number})',
                extra={'items': payload},
                data_only=True,  # True adds content-available, title/body adds alert
            )
        
        # Android device - keep current data-only behavior
        return self.send_notification(
            NotificationType.VOICEMAIL_RECEIVED,
            extra={'items': payload},
            data_only=True,
        )

    def messageReceived(self, data: dict[str, Any]) -> NotificationSentStatusDict:
        payload = data | {'notification_timestamp': generate_timestamp()}
        
        # iOS needs alert for killed state, Android works fine with data-only
        if self._can_send_to_apn(self.external_tokens):
            # iOS device - send hybrid notification (alert + content-available)
            alias = payload.get('alias', 'Someone')
            content = payload.get('content', 'New message')
            
            return self.send_notification(
                NotificationType.MESSAGE_RECEIVED,
                message_title=f'New Message from {alias}',
                message_body=content[:100],  # Truncate long messages
                extra={'items': payload},
                data_only=True,  # True adds content-available, title/body adds alert
            )
        
        # Android device - keep current data-only behavior
        return self.send_notification(
            NotificationType.MESSAGE_RECEIVED,
            extra={'items': payload},
            data_only=True,
        )

    def missedCall(self, data: dict[str, Any]) -> NotificationSentStatusDict:
        payload = {
            'notification_timestamp': generate_timestamp(),
            'caller_id_name': data['caller_id_name'],
            'caller_id_number': data['caller_id_number'],
        }
        
        # iOS needs alert for killed state, Android works fine with data-only
        if self._can_send_to_apn(self.external_tokens):
            # iOS device - send hybrid notification (alert + content-available)
            caller_name = data.get('caller_id_name', 'Unknown')
            caller_number = data.get('caller_id_number', '')
            
            return self.send_notification(
                NotificationType.MISSED_CALL,
                message_title='Missed Call',
                message_body=f'From: {caller_name} ({caller_number})',
                extra={'items': payload},
                data_only=True,  # True adds content-available, title/body adds alert
            )
        
        # Android device - keep current data-only behavior
        return self.send_notification(
            NotificationType.MISSED_CALL,
            extra={'items': payload},
            data_only=True,
        )

    def send_notification(
        self,
        notification_type: NotificationType | str,
        message_title: str | None = None,
        message_body: str | None = None,
        extra: dict[str, Any] | None = None,
        data_only: bool = False,
    ) -> NotificationSentStatusDict:
        extra = extra or {}
        data = cast(
            NotificationPayload,
            {
                'notification_type': notification_type,
                'items': extra.pop('items', {}),
            }
            | extra,
        )

        if data_only:
            # provide explicit data_only flag in notification payload
            # to help mobile app distinguish between data-only and normal notifications
            data['items']['data_only'] = True

        if self._can_send_to_apn(self.external_tokens):
            with requests_automatic_hook_retry(self.task):
                apn_response = self._send_via_apn(
                    message_title, message_body, data, data_only
                )
                return {
                    'success': True,  # error would be raised on failure
                    'protocol_used': 'apns',
                    'full_response': apn_response,
                }
        else:
            try:
                fcm_response = self._send_via_fcm(
                    message_title, message_body, data, data_only
                )
                return {
                    'success': fcm_response['success'] >= 1,
                    'protocol_used': 'fcm',
                    'full_response': fcm_response,
                }
            except RetryAfterException as e:
                raise HookRetry({"error": str(e)})

    @staticmethod
    def _can_send_to_apn(external_tokens: ExternalMobileDict) -> bool:
        return bool(
            (
                external_tokens.get('apns_voip_token')
                or external_tokens.get('apns_notification_token')
            )
            or external_tokens.get('apns_token')
        )

    def _send_via_fcm(
        self,
        message_title: str | None,
        message_body: str | None,
        data: NotificationPayload,
        data_only: bool,
    ) -> FcmResponseDict:
        logger.debug(
            'Sending push notification through FCM(type=%s, title=%s, body=%s, data_only=%s)',
            data['notification_type'],
            message_title,
            message_body,
            data_only,
        )
        fcm_service_account_info: dict
        fcm_api_key: str
        has_api_key = bool(self.external_config.get('fcm_api_key'))
        has_service_account_info = bool(
            self.external_config.get('fcm_service_account_info')
        )
        legacy_fcm = True

        if has_service_account_info:
            fcm_service_account_info_raw = self.external_config[
                'fcm_service_account_info'
            ]
            fcm_service_account_info = json.loads(fcm_service_account_info_raw)
            fcm_end_point = FCMNotification.FCM_END_POINT
            legacy_fcm = False
            logger.debug('Using FCM v1 client')
        elif has_api_key:
            fcm_api_key = self.external_config['fcm_api_key']
            fcm_end_point = FCMNotificationLegacy.FCM_END_POINT
            logger.debug('Using FCM legacy client')
            warnings.warn(
                "Using Firebase Cloud Messaging Legacy Client will be deprecated "
                "in June 2024. Please generate new credentials and use the service account "
                "information file instead. \n"
                "See https://firebase.google.com/docs/cloud-messaging"
                "/migrate-v1#provide-credentials-manually",
                FutureWarning,
            )
        elif self.jwt:
            fcm_api_key = self.jwt
            fcm_end_point = self.config['mobile_fcm_notification_end_point']
            logger.debug('Using FCM legacy client with JWT')
        else:
            raise Exception(
                'Unable to send notification to FCM: no valid authorization'
                'found to be sent to FCM'
            )

        push_service: FCMNotificationProtocol
        if legacy_fcm:
            push_service = FCMNotificationLegacy(api_key=fcm_api_key)
        else:
            push_service = FCMNotification(
                service_account_info=fcm_service_account_info
            )

        push_service.FCM_END_POINT = fcm_end_point

        notification_type = data['notification_type']

        if legacy_fcm:
            notify_kwargs = {
                'registration_id': self.external_tokens['token'],
                'data_message': data,
                'time_to_live': 0,
            }
        else:
            data_ = dict(data)
            # data payload must be serialized into a string
            if data_payload := data.get('items', None):
                data_['items'] = json.dumps(
                    data_payload, separators=(',', ':'), sort_keys=True
                )
            else:
                data_['items'] = ""

            notify_kwargs = {
                'registration_token': self.external_tokens['token'],
                'data_message': data_,
                'time_to_live': 0,
            }

        # special treatment of some notification types
        if notification_type == NotificationType.INCOMING_CALL:
            notification = push_service.notify_single_device(
                low_priority=False,
                **notify_kwargs,
            )
        elif notification_type == NotificationType.CANCEL_INCOMING_CALL:
            notification = push_service.single_device_data_message(
                android_channel_id=DEFAULT_ANDROID_CHANNEL_ID,
                **notify_kwargs,
            )
        else:
            if data_only:
                # data-only notification need high priority
                # and do not include `android.notification` attributes
                # TODO: remove android_channel_id
                #  does not seem useful since `android.notification`
                #  is not included in request for data messages
                logger.debug(
                    'push notification(type=%s) sent as data-only message',
                    notification_type,
                )
                notify_kwargs['low_priority'] = False
                notification = push_service.single_device_data_message(
                    android_channel_id=DEFAULT_ANDROID_CHANNEL_ID,
                    **notify_kwargs,
                )
            else:
                if message_title:
                    notify_kwargs['message_title'] = message_title
                if message_body:
                    notify_kwargs['message_body'] = message_body

                notification = push_service.notify_single_device(
                    android_channel_id=DEFAULT_ANDROID_CHANNEL_ID,
                    badge=1,
                    **notify_kwargs,
                )

        if notification.get('failure') != 0:
            logger.error('Error sending push notification to FCM: %s', notification)

        return notification

    @contextmanager
    def _apn_push_client(
        self, cert: str | None = None
    ) -> Generator[httpx.Client, None, None]:
        headers = {
            'apns-expiration': "0",
            'User-Agent': 'wazo-webhookd',
        }

        yield httpx.Client(
            http2=True,
            headers=headers,
            verify=True,
            cert=cert,
            timeout=REQUEST_TIMEOUTS,
        )

    def _send_via_apn(
        self,
        message_title: str | None,
        message_body: str | None,
        data: NotificationPayload,
        data_only: bool,
    ):
        headers, payload, token = self._create_apn_message(
            message_title, message_body, data, data_only
        )

        use_sandbox = self.external_config.get('use_sandbox', False)

        if use_sandbox:
            headers['X-Use-Sandbox'] = '1'

        if self.jwt:
            headers['Authorization'] = f'Bearer {self.jwt}'

        apn_certificate = self.external_config.get('ios_apn_certificate', None)
        apn_private = self.external_config.get('ios_apn_private', None)

        host = self.config['mobile_apns_host']
        if use_sandbox and host == 'api.push.apple.com':
            host = 'api.sandbox.push.apple.com'

        url = f"https://{host}:{self.config['mobile_apns_port']}/3/device/{token}"

        with self._certificate_filename(
            apn_certificate, apn_private
        ) as apn_cert_filename:
            logger.debug(
                'Sending push notification to APNS: POST %s, headers: %s,'
                'certificate: %s, payload: %s',
                url,
                headers,
                apn_cert_filename,
                payload,
            )
            with self._apn_push_client(cert=apn_cert_filename) as client:
                response = client.post(
                    url,
                    headers=headers,
                    json=payload,
                )
        response.raise_for_status()
        return requests_automatic_detail(response)

    def _create_apn_message(
        self,
        message_title: str | None,
        message_body: str | None,
        data: NotificationPayload,
        data_only: bool,
    ):
        apns_call_topic = self.config['mobile_apns_call_topic']
        apns_default_topic = self.config['mobile_apns_default_topic']

        if (
            notification_type := data['notification_type']
        ) == NotificationType.INCOMING_CALL:
            headers = {
                'apns-topic': apns_call_topic,
                'apns-push-type': 'voip',
                'apns-priority': '10',
            }
            payload = cast(
                ApnsPayload,
                {
                    'aps': {'alert': data, 'badge': 1},
                    **data,
                },
            )
        elif notification_type == NotificationType.CANCEL_INCOMING_CALL:
            headers = {
                'apns-topic': apns_default_topic,
                'apns-push-type': 'alert',
                'apns-priority': '5',
            }
            payload = cast(
                ApnsPayload,
                {
                    'aps': {"badge": 1, "sound": "default", "content-available": 1},
                    **data,
                },
            )
        else:
            headers = {
                'apns-topic': apns_default_topic,
                'apns-push-type': 'alert',
                'apns-priority': '5',
            }
            payload = cast(
                ApnsPayload,
                {
                    'aps': {'badge': 1, 'sound': "default"},
                    **data,
                },
            )

            if data_only:
                payload['aps']['content-available'] = 1
            
            if message_title or message_body:  # Changed from elif to if
                alert = {}
                if message_title:
                    alert['title'] = message_title
                if message_body:
                    alert['body'] = message_body
                payload['aps']['alert'] = alert

        if notification_type == NotificationType.INCOMING_CALL:
            # TODO(pc-m): The apns_voip_token was added in 20.05
            # the `or self.external_tokens["apns_token"]` should be removed when we stop
            # supporting wazo 20.XX
            token = (
                self.external_tokens.get("apns_voip_token")
                or self.external_tokens["apns_token"]
            )
        else:
            try:
                token = self.external_tokens['apns_notification_token']
            except KeyError:
                details = {
                    'message': 'Mobile application did not upload external '
                    'auth token `apns_notification_token`',
                }
                raise NotificationError(details)

        return headers, payload, token

    @staticmethod
    @contextmanager
    def _certificate_filename(
        certificate: str | None, private_key: str | None
    ) -> Generator[str | None, None, None]:
        if certificate and private_key:
            with tempfile.NamedTemporaryFile(mode="w+") as cert_file:
                cert_file.write(certificate + "\r\n")
                cert_file.write(private_key)
                cert_file.flush()

                yield cert_file.name
        else:
            yield None
