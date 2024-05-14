# Copyright 2023-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import uuid
from functools import partial

import pytest
import requests
from mockserver import MockServerClient
from wazo_test_helpers import until
from wazo_webhookd_client.exceptions import WebhookdError

from .helpers.base import (
    MASTER_TOKEN,
    PRIVATE_KEY,
    USER_1_UUID,
    USERS_TENANT,
    BaseIntegrationTest,
)
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

    def test_can_send_notification_android_legacy(self) -> None:
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


class TestNotificationsFCMv1(BaseIntegrationTest):
    asset = 'base'
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

    def test_can_send_notification_android_v1(self) -> None:
        fcm_account_info = {
            "type": "service_account",
            "project_id": "project-123",
            "private_key_id": uuid.uuid4().hex,
            "private_key": PRIVATE_KEY,
            "client_email": "project-123@project-123.iam.gserviceaccount.com",
            "client_id": "0" * 21,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": (
                "https://www.googleapis.com/robot/v1/metadata/"
                "x509/project-123%40project-123.iam.gserviceaccount.com"
            ),
            "universe_domain": "googleapis.com",
        }

        fake_token = {
            "access_token": "valid-access-token",
            "scope": "",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        auth = self.make_auth()
        auth.set_external_config(
            {
                'mobile': {
                    'fcm_service_account_info': json.dumps(fcm_account_info),
                    'is_sandbox': False,
                }
            }
        )
        oauth2_third_party = MockServerClient(
            f'http://127.0.0.1:{self.service_port(443, "oauth2.googleapis.com")}'
        )
        oauth2_third_party.reset()
        oauth2_third_party.mock_any_response(
            {
                'httpRequest': {
                    'method': 'POST',
                    'path': '/token',
                },
                'httpResponse': {
                    'statusCode': 200,
                    'body': json.dumps(fake_token),
                },
            }
        )

        fcm_third_party = MockServerClient(
            f'http://127.0.0.1:{self.service_port(443, "fcm.googleapis.com")}'
        )
        fcm_third_party.reset()
        expected_payload_body = {
            'message': {
                'data': {
                    'notification_type': 'plugin',
                    'plugin': 'test',
                    'items': '',
                },
                'android': {
                    'priority': 'high',
                    'ttl': '0s',
                    'notification': {
                        'channel_id': 'io.wazo.songbird',
                        'notification_count': 1,
                        'body': 'test message',
                        'title': 'test title',
                    },
                },
                'token': 'token-android',
            }
        }
        fcm_third_party.mock_any_response(
            {
                'httpRequest': {
                    'path': '/v1/projects/project-123/messages:send',
                    'body': {
                        'type': 'STRING',
                        'string': json.dumps(
                            expected_payload_body, separators=(',', ':'), sort_keys=True
                        ),
                    },
                },
                'httpResponse': {
                    'statusCode': 200,
                    'body': json.dumps({'name': 'message-id-plugin-test'}),
                },
            }
        )

        self.auth.set_external_auth({'token': 'token-android', 'apns_token': None})

        webhookd = self.make_webhookd(MASTER_TOKEN, USERS_TENANT)

        test_notification = {
            'notification_type': "plugin",
            'user_uuid': USER_1_UUID,
            'title': 'test title',
            'body': 'test message',
            'extra': {
                'plugin': "test",
            },
        }
        webhookd.mobile_notifications.send(test_notification)

        verify_called = partial(
            fcm_third_party.verify,
            request={
                'path': '/v1/projects/project-123/messages:send',
                'body': {
                    'type': 'string',
                    'string': json.dumps(
                        expected_payload_body, separators=(',', ':'), sort_keys=True
                    ),
                },
            },
        )
        until.return_(verify_called, timeout=15, interval=0.5)
