# Copyright 2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
import json
from functools import partial

import pytest
import requests
from mockserver import MockServerClient
from wazo_test_helpers import until
from wazo_webhookd_client.exceptions import WebhookdError

from .helpers.base import BaseIntegrationTest, USERS_TENANT
from .helpers.base import MASTER_TOKEN, USER_1_UUID
from .helpers.wait_strategy import ConnectedWaitStrategy


class TestNotifications(BaseIntegrationTest):
    asset = 'proxy'
    wait_strategy = ConnectedWaitStrategy()

    def setUp(self):
        super().setUp()
        self.auth = self.make_auth()
        requests.post(
            self.auth.url('0.1/users'),
            json={
                'email_address': 'foo@bar',
                'username': 'foobar',
                'password': 'secret',
                'uuid': USER_1_UUID,
            },
            headers={'Wazo-Tenant': USERS_TENANT},
        )

    def test_can_send_notification_invalid(self) -> None:
        webhookd = self.make_webhookd(MASTER_TOKEN, USERS_TENANT)
        self.auth.reset_external_auth()
        self.auth.set_external_auth({'token': 'token-android', 'apns_token': None})

        test_notification = {
            'notification_type': "incomingCall",
            'user_uuid': '',
            'extra': '',
        }
        with pytest.raises(WebhookdError) as exec_info:
            webhookd.mobile_notifications.send(test_notification)

        error = exec_info.value
        assert error.status_code == 400
        assert error.details == {
            'body': ['Missing data for required field.'],
            'title': ['Missing data for required field.'],
            'notification_type': ['The type "incomingCall" is a reserved type.'],
            'extra': ['Not a valid mapping type.'],
            'user_uuid': ['Length must be 36.'],
        }

    def test_can_send_notification_android(self) -> None:
        third_party = MockServerClient(
            f'http://127.0.0.1:{self.service_port(443, "fcm.proxy.example.com")}'
        )
        third_party.reset()
        expected_payload_body = {
            'data': {
                'items': {},
                'notification_type': 'plugin',
                'plugin': {
                    "action": "test",
                    "entityId": "test-plugin",
                    "id": "test",
                    "payload": {},
                },
            },
            'notification': {
                "android_channel_id": "io.wazo.songbird",
                "badge": 1,
                "body": "test message",
                "title": "test title",
            },
            'priority': 'high',
            'to': 'token-android',
        }
        third_party.mock_any_response(
            {
                'httpRequest': {
                    'path': '/fcm/send',
                    'body': {
                        'type': 'STRING',
                        'string': json.dumps(
                            expected_payload_body, separators=(',', ':')
                        ),
                    },
                },
                'httpResponse': {
                    'statusCode': 200,
                    'body': json.dumps({'message_id': 'message-id-plugin-test'}),
                },
            }
        )

        self.auth.reset_external_auth()
        self.auth.set_external_config(
            {'mobile': {'token': 'FCM_API_KEY'}, 'is_sandbox': False}
        )
        self.auth.set_external_auth({'token': 'token-android', 'apns_token': None})

        webhookd = self.make_webhookd(MASTER_TOKEN, USERS_TENANT)

        test_notification = {
            'notification_type': "plugin",
            'user_uuid': USER_1_UUID,
            'title': 'test title',
            'body': 'test message',
            'extra': {
                'plugin': {
                    "id": "test",
                    "entityId": "test-plugin",
                    "action": "test",
                    "payload": {},
                },
            },
        }
        webhookd.mobile_notifications.send(test_notification)

        verify_called = partial(
            third_party.verify,
            request={
                'path': '/fcm/send',
                'body': {
                    'type': 'string',
                    'string': json.dumps(expected_payload_body, separators=(',', ':')),
                },
            },
        )
        until.return_(verify_called, timeout=15, interval=0.5)

    def test_can_send_notification_ios(self) -> None:
        with open(self.assets_root + "/fake-apple-ca/certs/client.crt") as f:
            ios_apn_certificate = f.read()

        with open(self.assets_root + "/fake-apple-ca/certs/client.key") as f:
            ios_apn_key = f.read()

        self.auth.reset_external_auth()
        self.auth.set_external_auth(
            {
                'token': 'token-android',
                'apns_token': 'apns-voip-token',
                'apns_voip_token': 'apns-voip-token',
                'apns_notification_token': 'apns-notification-token',
            }
        )
        self.auth.set_external_config(
            {
                'mobile': {
                    'fcm_api_key': '',
                    'ios_apn_certificate': ios_apn_certificate,
                    'ios_apn_private': ios_apn_key,
                    'is_sandbox': False,
                }
            }
        )
        apns_third_party = MockServerClient(
            f'http://127.0.0.1:{self.service_port(1080, "third-party-http")}'
        )
        apns_third_party.reset()
        apns_third_party.mock_simple_response(
            path='/3/device/apns-voip-token',
            responseBody={'tracker': 'tracker-voip'},
            statusCode=200,
        )
        apns_third_party.mock_simple_response(
            path='/3/device/apns-notification-token',
            responseBody={'tracker': 'tracker-notification'},
            statusCode=200,
        )

        webhookd = self.make_webhookd(MASTER_TOKEN, USERS_TENANT)

        test_notification = {
            'notification_type': "plugin",
            'user_uuid': USER_1_UUID,
            'title': 'test title',
            'body': 'test message',
            'extra': {
                'plugin': {
                    "id": "test",
                    "entityId": "test-plugin",
                    "action": "test",
                    "payload": {},
                },
            },
        }
        webhookd.mobile_notifications.send(test_notification)
        test = {
            'aps': {
                'badge': 1,
                'sound': 'default',
                'alert': {'title': 'test title', 'body': 'test message'},
            },
            'notification_type': 'plugin',
            'items': {},
            'plugin': {
                'id': 'test',
                'entityId': 'test-plugin',
                'action': 'test',
                'payload': {},
            },
        }
        verify_called = partial(
            apns_third_party.verify,
            request={
                'path': '/3/device/apns-notification-token',
                'body': {
                    'type': 'string',
                    'string': json.dumps(test),
                },
            },
        )
        until.return_(verify_called, timeout=15, interval=0.5)
