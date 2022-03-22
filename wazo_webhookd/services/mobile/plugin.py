# Copyright 2017-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import httpx
import logging
import tempfile
import uuid

from contextlib import contextmanager
from pyfcm import FCMNotification
from pyfcm.errors import RetryAfterException

from wazo_auth_client import Client as AuthClient
from wazo_webhookd.plugins.subscription.service import SubscriptionService
from wazo_webhookd.services.helpers import (
    HookExpectedError,
    HookRetry,
    requests_automatic_hook_retry,
    requests_automatic_detail,
)
from .exceptions import NotificationError

logger = logging.getLogger(__name__)

REQUESTS_TIMEOUT = (10, 15, 15)  # seconds

MAP_NAME_TO_NOTIFICATION_TYPE = {
    'user_voicemail_message_created': 'voicemailReceived',
    'call_push_notification': 'incomingCall',
    'call_cancel_push_notification': 'cancelIncomingCall',
    'chatd_user_room_message_created': 'messageReceived',
}


class Service:
    def load(self, dependencies):
        bus_consumer = dependencies['bus_consumer']
        self._config = dependencies['config']
        self.subscription_service = SubscriptionService(self._config)
        bus_consumer.subscribe_to_event_names(
            uuid=str(uuid.uuid4()),
            event_names=['auth_user_external_auth_added'],
            # tenant_uuid=None,
            user_uuid=None,
            wazo_uuid=None,
            callback=self.on_external_auth_added,
        )
        bus_consumer.subscribe_to_event_names(
            uuid=str(uuid.uuid4()),
            event_names=['auth_user_external_auth_deleted'],
            # tenant_uuid=None,
            user_uuid=None,
            wazo_uuid=None,
            callback=self.on_external_auth_deleted,
        )
        logger.info('Mobile push notification plugin is started')

    def on_external_auth_added(self, body, event):
        if body['data'].get('external_auth_name') == 'mobile':
            user_uuid = body['data']['user_uuid']
            # TODO(sileht): Should come with the event
            tenant_uuid = self.get_tenant_uuid(user_uuid)
            self.subscription_service.create(
                {
                    'name': (
                        'Push notification mobile for user '
                        '{}/{}'.format(tenant_uuid, user_uuid)
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

    def on_external_auth_deleted(self, body, event):
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

    def get_tenant_uuid(self, user_uuid):
        auth, jwt = self.get_auth(self._config)
        return auth.users.get(user_uuid)["tenant_uuid"]

    @classmethod
    def get_auth(cls, config):
        auth_config = dict(config['auth'])
        # FIXME(sileht): Keep the certificate
        auth_config['verify_certificate'] = False
        auth = AuthClient(**auth_config)
        token = auth.token.new('wazo_user', expiration=3600)
        auth.set_token(token["token"])
        jwt = token.get("metadata", {}).get("jwt", "")
        auth.username = None
        auth.password = None
        return (auth, jwt)

    @classmethod
    def get_external_data(cls, config, user_uuid):
        auth, jwt = cls.get_auth(config)
        external_tokens = auth.external.get('mobile', user_uuid)
        tenant_uuid = auth.users.get(user_uuid)['tenant_uuid']
        external_config = auth.external.get_config('mobile', tenant_uuid)

        return (external_tokens, external_config, jwt)

    @classmethod
    def run(cls, task, config, subscription, event):
        user_uuid = subscription['events_user_uuid']
        if not user_uuid:
            raise HookExpectedError("subscription doesn't have events_user_uuid set")

        # TODO(sileht): We should also filter on tenant_uuid
        # tenant_uuid = subscription.get('events_tenant_uuid')
        if (
            event['data'].get('user_uuid') == user_uuid
            # and event['data']['tenant_uuid'] == tenant_uuid
            and event['name'] == 'chatd_user_room_message_created'
        ):
            return

        external_tokens, external_config, jwt = cls.get_external_data(config, user_uuid)
        push = PushNotification(task, config, external_tokens, external_config, jwt)

        data = event.get('data')
        name = event.get('name')

        notification_type = MAP_NAME_TO_NOTIFICATION_TYPE.get(name)
        if notification_type:
            return getattr(push, notification_type)(data)


class PushNotification:
    def __init__(self, task, config, external_tokens, external_config, jwt):
        self.task = task
        self.config = config
        self.external_tokens = external_tokens
        self.external_config = external_config
        self.jwt = jwt

    def cancelIncomingCall(self, data):
        return self._send_notification(
            'cancelIncomingCall',
            None,  # Message title
            None,  # Message body
            'wazo-notification-cancel-call',
            data,
        )

    def incomingCall(self, data):
        return self._send_notification(
            'incomingCall',
            'Incoming Call',
            'From: {}'.format(data['peer_caller_id_number']),
            'wazo-notification-call',
            data,
        )

    def voicemailReceived(self, data):
        return self._send_notification(
            'voicemailReceived',
            'New voicemail',
            'From: {}'.format(data['message']['caller_id_num']),
            'wazo-notification-voicemail',
            data,
        )

    def messageReceived(self, data):
        return self._send_notification(
            'messageReceived',
            data['alias'],
            data['content'],
            'wazo-notification-chat',
            data,
        )

    def _send_notification(
        self, notification_type, message_title, message_body, channel_id, items
    ):
        data = {'notification_type': notification_type, 'items': items}
        if self._can_send_to_apn(self.external_tokens):
            with requests_automatic_hook_retry(self.task):
                return self._send_via_apn(message_title, message_body, channel_id, data)
        else:
            try:
                return self._send_via_fcm(message_title, message_body, channel_id, data)
            except RetryAfterException as e:
                raise HookRetry({"error": str(e)})

    @staticmethod
    def _can_send_to_apn(external_tokens):
        return bool(
            (
                external_tokens.get('apns_voip_token')
                or external_tokens.get('apns_notification_token')
            )
            or external_tokens.get('apns_token')
        )

    def _send_via_fcm(self, message_title, message_body, channel_id, data):
        logger.debug(
            'Sending push notification to Android: %s, %s'
            % (message_title, message_body)
        )

        push_service = FCMNotification(api_key=self.external_config['fcm_api_key'])

        notify_kwargs = {
            'registration_id': self.external_tokens['token'],
            'data_message': data,
        }
        if channel_id == 'wazo-notification-call':
            notify_kwargs['extra_notification_kwargs'] = {'priority': 'high'}
        else:
            notify_kwargs['badge'] = 1
            notify_kwargs['extra_notification_kwargs'] = {
                'android_channel_id': channel_id
            }
            if message_title:
                notify_kwargs['message_title'] = message_title
            if message_body:
                notify_kwargs['message_body'] = message_body

        notification = push_service.notify_single_device(**notify_kwargs)
        if notification.get('failure') != 0:
            logger.error('Error to send push notification: %s', notification)
        return notification

    @property
    def _apn_push_client(self):
        headers = {
            'apns-expiration': "0",
            'User-Agent': 'wazo-webhookd',
        }

        return httpx.Client(
            http_versions=['HTTP/2', 'HTTP/1.1'],
            headers=headers,
            verify=True,
            trust_env=False,
            timeout=REQUESTS_TIMEOUT,
        )

    def _send_via_apn(self, message_title, message_body, channel_id, data):
        headers, payload, token = self._create_apn_message(
            message_title, message_body, channel_id, data
        )

        use_sandbox = self.external_config.get('use_sandbox', False)

        if use_sandbox:
            headers['X-Use-Sandbox'] = '1'

        if self.jwt:
            headers['Authorization'] = 'Bearer ' + self.jwt

        apn_certificate = self.external_config.get('ios_apn_certificate', None)
        apn_private = self.external_config.get('ios_apn_private', None)

        host = self.config['mobile_apns_host']
        if use_sandbox and host == 'api.push.apple.com':
            host = 'api.sandbox.push.apple.com'

        url = "https://{}:{}/3/device/{}".format(
            host, self.config['mobile_apns_port'], token
        )

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
            response = self._apn_push_client.post(
                url,
                cert=apn_cert_filename,
                headers=headers,
                json=payload,
            )
        response.raise_for_status()
        return requests_automatic_detail(response)

    def _create_apn_message(self, message_title, message_body, channel_id, data):
        if channel_id == 'wazo-notification-call':
            headers = {
                'apns-topic': 'io.wazo.songbird.voip',
                'apns-push-type': 'voip',
                'apns-priority': '10',
            }
            payload = {
                'aps': {'alert': data, 'badge': 1},
                **data,
            }
            # TODO(pc-m): The apns_voip_token was added in 20.05
            # the `or self.external_tokens["apns_token"]` should be removed when we stop
            # supporting wazo 20.XX
            token = (
                self.external_tokens.get("apns_voip_token")
                or self.external_tokens["apns_token"]
            )
        else:
            headers = {
                'apns-topic': 'io.wazo.songbird',
                'apns-push-type': 'alert',
                'apns-priority': '5',
            }
            payload = {
                'aps': {
                    'badge': 1,
                    'sound': "default",
                },
                **data,
            }

            if message_title or message_body:
                alert = {}
                if message_title:
                    alert['title'] = message_title
                if message_body:
                    alert['body'] = message_body
                payload['aps']['alert'] = alert

            try:
                token = self.external_tokens['apns_notification_token']
            except KeyError:
                details = {
                    'message': 'Mobile application did not upload external auth token `apns_notification_token`',
                }
                raise NotificationError(details)
        return headers, payload, token

    @staticmethod
    @contextmanager
    def _certificate_filename(certificate, private_key):
        if certificate and private_key:
            with tempfile.NamedTemporaryFile(mode="w+") as cert_file:
                cert_file.write(certificate + "\r\n")
                cert_file.write(private_key)
                cert_file.flush()

                yield cert_file.name
        else:
            yield None
