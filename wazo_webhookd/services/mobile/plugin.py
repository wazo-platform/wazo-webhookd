# Copyright 2017-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+
from __future__ import annotations

from collections.abc import Generator
from enum import Enum
from typing import Any, cast, TypedDict, TYPE_CHECKING, Union, Literal

import httpx
import logging
import tempfile

from contextlib import contextmanager

from celery import Task
from pyfcm import FCMNotification
from pyfcm.errors import RetryAfterException

from wazo_auth_client import Client as AuthClient

from wazo_webhookd.plugins.subscription.service import SubscriptionService
from wazo_webhookd.services.helpers import (
    HookExpectedError,
    HookRetry,
    requests_automatic_hook_retry,
    requests_automatic_detail,
    RequestDetailsDict,
)
from .exceptions import NotificationError
from ...database.models import Subscription

if TYPE_CHECKING:
    from wazo_auth_client.types import TokenDict
    from ...types import WebhookdConfigDict, ServicePluginDependencyDict

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
    ios_apn_certificate: str
    ios_apn_private: str
    use_sandbox: bool


class BaseNotificationPayload(TypedDict):
    notification_type: str
    items: dict[str, Any]


NotificationPayload = Union[BaseNotificationPayload, dict[str, Any]]


ApsContentDict = TypedDict(
    'ApsContentDict',
    {
        'badge': int,
        'sound': str,
        'content-available': str,
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
    topic_message_id: Union[str, None]


class NotificationSentStatusDict(TypedDict):
    success: bool
    protocol_used: Literal['apns', 'fcm']
    full_response: Union[FcmResponseDict, RequestDetailsDict]


REQUEST_TIMEOUTS = httpx.Timeout(connect=10, read=15, write=15, pool=None)

DEFAULT_ANDROID_CHANNEL_ID = 'io.wazo.songbird'


class NotificationType(
    str, Enum
):  # TODO: StrEnum would be better, when we have Python 3.11
    MESSAGE_RECEIVED = 'messageReceived'
    VOICEMAIL_RECEIVED = 'voicemailReceived'
    INCOMING_CALL = 'incomingCall'
    CANCEL_INCOMING_CALL = 'cancelIncomingCall'
    PLUGIN = 'plugin'


RESERVED_NOTIFICATION_TYPES = (
    NotificationType.MESSAGE_RECEIVED,
    NotificationType.VOICEMAIL_RECEIVED,
    NotificationType.INCOMING_CALL,
    NotificationType.CANCEL_INCOMING_CALL,
)

MAP_NAME_TO_NOTIFICATION_TYPE = {
    'user_voicemail_message_created': NotificationType.VOICEMAIL_RECEIVED,
    'call_push_notification': NotificationType.INCOMING_CALL,
    'call_cancel_push_notification': NotificationType.CANCEL_INCOMING_CALL,
    'chatd_user_room_message_created': NotificationType.MESSAGE_RECEIVED,
}


class Service:
    subscription_service: SubscriptionService
    _config: WebhookdConfigDict

    def load(self, dependencies: ServicePluginDependencyDict) -> None:
        bus_consumer = dependencies['bus_consumer']
        self._config = dependencies['config']
        self.subscription_service = SubscriptionService(self._config)
        bus_consumer.subscribe(
            'auth_user_external_auth_added',
            self.on_external_auth_added,
            headers={'x-internal': True},
        )
        bus_consumer.subscribe(
            'auth_user_external_auth_deleted',
            self.on_external_auth_deleted,
            headers={'x-internal': True},
        )
        logger.info('Mobile push notification plugin is started')

    def on_external_auth_added(self, body):
        if body['data'].get('external_auth_name') == 'mobile':
            user_uuid = body['data']['user_uuid']
            # TODO(sileht): Should come with the event
            tenant_uuid = self.get_tenant_uuid(user_uuid)
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
                    ],
                    'events_user_uuid': user_uuid,
                    # 'events_tenant_uuid': tenant_uuid,
                    'owner_user_uuid': user_uuid,
                    'owner_tenant_uuid': tenant_uuid,
                    'config': {},
                    'metadata_': {'mobile': 'true'},
                }
            )
            logger.info('User registered: %s/%s', tenant_uuid, user_uuid)

    def on_external_auth_deleted(self, body: dict[str, Any]) -> None:
        if body['data'].get('external_auth_name') == 'mobile':
            user_uuid = body['data']['user_uuid']
            # TODO(sileht): Should come with the event
            tenant_uuid = self.get_tenant_uuid(user_uuid)
            subscriptions = self.subscription_service.list(
                owner_user_uuid=user_uuid,
                owner_tenant_uuids=[tenant_uuid],
                search_metadata={'mobile': 'true'},
            )
            for subscription in subscriptions:
                self.subscription_service.delete(subscription.uuid)
            logger.info('User unregistered: %s/%s', tenant_uuid, user_uuid)

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
        external_config: ExternalConfigDict = auth.external.get_config(
            'mobile', tenant_uuid
        )

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

        if notification_type := MAP_NAME_TO_NOTIFICATION_TYPE.get(name):
            return getattr(push, notification_type)(data)
        return None


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
        return self.send_notification(
            NotificationType.CANCEL_INCOMING_CALL,
            None,  # Message title
            None,  # Message body
            {'items': data},
        )

    def incomingCall(self, data: dict[str, Any]) -> NotificationSentStatusDict:
        return self.send_notification(
            NotificationType.INCOMING_CALL,
            'Incoming Call',
            f'From: {data["peer_caller_id_number"]}',
            {'items': data},
        )

    def voicemailReceived(self, data: dict[str, Any]) -> NotificationSentStatusDict:
        return self.send_notification(
            NotificationType.VOICEMAIL_RECEIVED,
            'New voicemail',
            f'From: {data["message"]["caller_id_num"]}',
            {'items': data},
        )

    def messageReceived(self, data: dict[str, Any]) -> NotificationSentStatusDict:
        return self.send_notification(
            NotificationType.MESSAGE_RECEIVED,
            data['alias'],
            data['content'],
            {'items': data},
        )

    def send_notification(
        self,
        notification_type: NotificationType | str,
        message_title: str | None,
        message_body: str | None,
        extra: dict[str, Any],
    ) -> NotificationSentStatusDict:
        data: NotificationPayload = {
            'notification_type': notification_type,
            'items': extra.pop('items', {}),
        } | extra
        if self._can_send_to_apn(self.external_tokens):
            with requests_automatic_hook_retry(self.task):
                apn_response = self._send_via_apn(message_title, message_body, data)
                return {
                    'success': True,  # error would be raised on failure
                    'protocol_used': 'apns',
                    'full_response': apn_response,
                }
        else:
            try:
                fcm_response = self._send_via_fcm(message_title, message_body, data)
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
    ) -> FcmResponseDict:
        logger.debug(
            'Sending push notification to Android: %s, %s',
            message_title,
            message_body,
        )
        notification_type = data['notification_type']
        fcm_api_key: str | None
        if self.config['mobile_fcm_notification_send_jwt_token']:
            if self.jwt:
                fcm_api_key = self.jwt
            else:
                logger.warning(
                    'fcm is configured to use the JWT token but no token available'
                )
                raise Exception('No configured JWT token')
        else:
            fcm_api_key = self.external_config.get('fcm_api_key')

        push_service = FCMNotification(api_key=fcm_api_key)
        push_service.FCM_END_POINT = self.config['mobile_fcm_notification_end_point']
        logger.debug(f'FCM endpoint: {push_service.FCM_END_POINT}')
        notify_kwargs = {
            'registration_id': self.external_tokens['token'],
            'data_message': data,
        }

        if notification_type == NotificationType.INCOMING_CALL:
            notification = push_service.notify_single_device(
                extra_notification_kwargs={'priority': 'high'},
                **notify_kwargs,
            )
        elif notification_type == NotificationType.CANCEL_INCOMING_CALL:
            notification = push_service.single_device_data_message(
                extra_notification_kwargs={
                    'android_channel_id': DEFAULT_ANDROID_CHANNEL_ID
                },
                **notify_kwargs,
            )
        else:
            if message_title:
                notify_kwargs['message_title'] = message_title
            if message_body:
                notify_kwargs['message_body'] = message_body

            notification = push_service.notify_single_device(
                extra_notification_kwargs={
                    'android_channel_id': DEFAULT_ANDROID_CHANNEL_ID
                },
                badge=1,
                **notify_kwargs,
            )

        if notification.get('failure') != 0:
            logger.error('Error to send push notification: %s', notification)
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
            trust_env=False,
            timeout=REQUEST_TIMEOUTS,
        )

    def _send_via_apn(
        self,
        message_title: str | None,
        message_body: str | None,
        data: NotificationPayload,
    ):
        headers, payload, token = self._create_apn_message(
            message_title, message_body, data
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

            if message_title or message_body:
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
