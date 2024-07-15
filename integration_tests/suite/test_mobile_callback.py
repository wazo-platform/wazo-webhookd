# Copyright 2017-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import functools
import json
import uuid

import requests
from hamcrest import (
    assert_that,
    contains_exactly,
    contains_inanyorder,
    contains_string,
    equal_to,
    has_entries,
    has_entry,
    has_item,
    instance_of,
)
from mockserver import MockServerClient as _MockServerClient
from wazo_test_helpers import until

from .helpers.base import (
    JWT_TENANT_0,
    MASTER_TOKEN,
    PRIVATE_KEY,
    USER_1_UUID,
    USER_2_UUID,
    USERS_TENANT,
    BaseIntegrationTest,
)
from .helpers.wait_strategy import ConnectedWaitStrategy

SOME_ROUTING_KEY = 'routing-key'


class MockServerClient(_MockServerClient):
    def get_requests(self, path: str):
        response = self._put('/retrieve?type=requests', {'path': path})
        response.raise_for_status()
        return response.json()

    def assert_verify(
        self, request, count: int | None = None, exact: bool | None = None
    ):
        try:
            assert self.verify(request, count=count, exact=exact)
        except Exception:
            raise AssertionError(
                f'Failed to verify {request} with count {count}(exact={exact})'
            )


class BaseMobileCallbackIntegrationTest(BaseIntegrationTest):
    wait_strategy = ConnectedWaitStrategy()

    @staticmethod
    def _wait_items(func, number=1):
        def check():
            logs = func()
            assert_that(logs['total'], equal_to(number))

        until.assert_(check, timeout=10, interval=0.5)

    def setUp(self):
        super().setUp()
        self.webhookd = self.make_webhookd(MASTER_TOKEN)
        self.bus = self.make_bus()
        self.auth = self.make_auth()

        self.auth.set_external_config(
            {
                'mobile': {
                    'is_sandbox': False,
                }
            }
        )

        self.auth.reset_external_auth()

        # create users
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
        requests.post(
            self.auth.url('0.1/users'),
            json={
                'email_address': 'foo@bar',
                'username': 'foobar',
                'password': 'secret',
                'uuid': USER_2_UUID,
            },
            headers={'Wazo-Tenant': USERS_TENANT},
        )

    def tearDown(self) -> None:
        super().tearDown()
        for subscription in self.webhookd.subscriptions.list(recurse=True)['items']:
            self.webhookd.subscriptions.delete(subscription['uuid'])

    def _given_mobile_subscription(self, user_uuid):
        # mobile user logs in
        self.bus.publish(
            {
                'name': 'auth_user_external_auth_added',
                'origin_uuid': 'my-origin-uuid',
                'data': {'external_auth_name': 'mobile', 'user_uuid': str(user_uuid)},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'auth_user_external_auth_added',
                'origin_uuid': 'my-origin-uuid',
            },
        )
        self._wait_items(
            functools.partial(self.webhookd.subscriptions.list, recurse=True)
        )
        subscriptions = self.webhookd.subscriptions.list(recurse=True)
        assert (
            subscription := next(
                (
                    s
                    for s in subscriptions['items']
                    if s['owner_user_uuid'] == user_uuid and s['service'] == 'mobile'
                ),
                None,
            )
        )

        assert subscription['events'] and 'user_missed_call' in subscription['events']

        return subscription


class TestMobileCallbackFCMProxy(BaseMobileCallbackIntegrationTest):
    """
    coverage for event-triggered mobile push notifications with FCM push proxy
    """

    asset = 'proxy'
    wait_strategy = ConnectedWaitStrategy()

    def setUp(self):
        super().setUp()
        self.third_party = MockServerClient(
            f'http://127.0.0.1:{self.service_port(443, "fcm.proxy.example.com")}'
        )
        self.third_party.reset()
        self.auth.set_external_auth({'token': 'token-android', 'apns_token': None})

    def test_incoming_call_workflow_fcm(self):
        # setup FCM API for incomingCall push notification request
        self.third_party.mock_any_response(
            {
                'httpRequest': {
                    'path': '/fcm/send',
                    'body': {
                        'type': 'JSON',
                        'json': {
                            'data': {
                                'items': json.dumps(
                                    {'peer_caller_id_number': 'caller-id'}
                                ),
                                'notification_type': 'incomingCall',
                            }
                        },
                        'matchType': 'ONLY_MATCHING_FIELDS',
                    },
                },
                'httpResponse': {
                    'statusCode': 200,
                    'body': json.dumps({'message_id': 'message-id-incoming-call'}),
                },
            }
        )
        # setup FCM API for cancelIncomingCall push notification request
        self.third_party.mock_any_response(
            {
                'httpRequest': {
                    'path': '/fcm/send',
                    'body': {
                        'type': 'JSON',
                        'json': {
                            'data': {
                                'items': json.dumps(
                                    {'peer_caller_id_number': 'caller-id'}
                                ),
                                'notification_type': 'cancelIncomingCall',
                            }
                        },
                        'matchType': 'ONLY_MATCHING_FIELDS',
                    },
                },
                'httpResponse': {
                    'statusCode': 200,
                    'body': json.dumps(
                        {'message_id': 'message-id-cancel-incoming-call'}
                    ),
                },
            }
        )

        # mobile user logs in
        self.bus.publish(
            {
                'name': 'auth_user_external_auth_added',
                'origin_uuid': 'my-origin-uuid',
                'data': {'external_auth_name': 'mobile', 'user_uuid': USER_1_UUID},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'auth_user_external_auth_added',
                'origin_uuid': 'my-origin-uuid',
            },
        )

        # expect new subscription for new mobile login
        self._wait_items(
            functools.partial(self.webhookd.subscriptions.list, recurse=True)
        )
        subscriptions = self.webhookd.subscriptions.list(recurse=True)
        assert_that(subscriptions['total'], equal_to(1))
        assert_that(
            subscriptions['items'][0],
            has_entries(
                name=f"Push notification mobile for user {USERS_TENANT}/{USER_1_UUID}",
                events=contains_inanyorder(
                    'chatd_user_room_message_created',
                    'call_push_notification',
                    'call_cancel_push_notification',
                    'user_voicemail_message_created',
                    'user_missed_call',
                ),
                owner_tenant_uuid=USERS_TENANT,
                owner_user_uuid=USER_1_UUID,
                service='mobile',
            ),
        )

        subscription = subscriptions['items'][0]

        # trigger bus event for incoming call push notification
        self.bus.publish(
            {
                'name': 'call_push_notification',
                'origin_uuid': 'my-origin-uuid',
                f'user_uuid:{USER_1_UUID}': True,
                'data': {'peer_caller_id_number': 'caller-id'},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'call_push_notification',
                'origin_uuid': 'my-origin-uuid',
                'tenant_uuid': USERS_TENANT,
                f'user_uuid:{USER_1_UUID}': True,
            },
        )

        self._wait_items(
            functools.partial(
                self.webhookd.subscriptions.get_logs, subscription["uuid"]
            )
        )

        # expect FCM API to receive request for push notif
        self.third_party.verify(
            request={
                'path': '/fcm/send',
                'headers': [
                    {'name': 'authorization', 'values': [f'key={JWT_TENANT_0}']},
                ],
            },
        )

        logs = self.webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], equal_to(1))
        assert_that(
            logs['items'][0],
            has_entries(
                status="success",
                detail=has_entry(
                    'full_response',
                    has_entry('topic_message_id', 'message-id-incoming-call'),
                ),
                attempts=1,
            ),
        )

        # Canceling the push notification
        self.bus.publish(
            {
                'name': 'call_cancel_push_notification',
                'origin_uuid': 'my-origin-uuid',
                f'user_uuid:{USER_1_UUID}': True,
                'data': {'peer_caller_id_number': 'caller-id'},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'call_push_notification',
                'origin_uuid': 'my-origin-uuid',
                'tenant_uuid': USERS_TENANT,
                f'user_uuid:{USER_1_UUID}': True,
            },
        )

        self._wait_items(
            functools.partial(
                self.webhookd.subscriptions.get_logs, subscription["uuid"]
            ),
            number=2,
        )

        logs = self.webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], equal_to(2))
        assert_that(
            logs['items'][0],
            has_entries(
                status="success",
                detail=has_entry(
                    'full_response',
                    has_entries(topic_message_id='message-id-cancel-incoming-call'),
                ),
                event=has_entries(name='call_cancel_push_notification'),
                attempts=1,
            ),
        )

        self.webhookd.subscriptions.delete(subscription["uuid"])

    def test_missed_call_notification(self):
        # user logs in
        subscription = self._given_mobile_subscription(USER_1_UUID)

        self.third_party.mock_any_response(
            {
                'httpRequest': {
                    'path': '/fcm/send',
                    'body': {
                        'type': 'JSON',
                        'json': {
                            'data': {
                                'items': json.dumps(
                                    {
                                        'caller_id_number': '12221114455',
                                        'caller_id_name': 'John Doe',
                                    }
                                ),
                                'notification_type': 'missedCall',
                            }
                        },
                        'matchType': 'ONLY_MATCHING_FIELDS',
                    },
                },
                'httpResponse': {
                    'statusCode': 200,
                    'body': json.dumps({'message_id': 'message-id-missed-call'}),
                },
            }
        )

        # mobile user misses a call
        self.bus.publish(
            {
                'name': 'user_missed_call',
                'origin_uuid': 'my-origin-uuid',
                'data': {
                    'user_uuid': f'{USER_1_UUID}',
                    'caller_user_uuid': 'ad5b78cf-6e15-45c7-9ef3-bec36e07e8d6',
                    'caller_id_name': 'John Doe',
                    'caller_id_number': '12221114455',
                    'dialed_extension': '8000',
                    'conversation_id': '1718908219.36',
                    'reason': 'no-answer',
                },
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'user_missed_call',
                'origin_uuid': 'my-origin-uuid',
                'tenant_uuid': USERS_TENANT,
                f'user_uuid:{USER_1_UUID}': True,
            },
        )

        def assert_subscription_logs():
            sbs = self.webhookd.subscriptions.get_logs(subscription["uuid"])
            assert sbs and sbs.get('items')

        until.assert_(assert_subscription_logs, timeout=10, interval=0.5)

        # expect FCM API to receive request for push notif
        self.third_party.verify(
            request={
                'path': '/fcm/send',
                'headers': [
                    {'name': 'authorization', 'values': [f'key={JWT_TENANT_0}']},
                ],
            },
        )

        logs = self.webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], equal_to(1))
        assert_that(
            logs['items'][0],
            has_entries(
                status="success",
                detail=has_entry(
                    'full_response',
                    has_entry('topic_message_id', 'message-id-missed-call'),
                ),
                attempts=1,
            ),
        )


class TestMobileCallback(BaseMobileCallbackIntegrationTest):
    asset = 'base'
    wait_strategy = ConnectedWaitStrategy()

    def setUp(self):
        super().setUp()


class TestMobileCallbackFCMLegacy(TestMobileCallback):
    def setUp(self):
        super().setUp()
        self.auth.set_external_auth({'token': 'token-android', 'apns_token': None})
        self.auth.set_external_config(
            {
                'mobile': {
                    'fcm_api_key': 'FCM_API_KEY',
                    'is_sandbox': False,
                }
            }
        )
        self.third_party = MockServerClient(
            f'http://127.0.0.1:{self.service_port(443, "fcm.googleapis.com")}'
        )
        self.third_party.reset()

    def test_incoming_call_workflow(self):
        # setup FCM incomingCall notification request
        self.third_party.mock_any_response(
            {
                'httpRequest': {
                    'path': '/fcm/send',
                    'body': {
                        'type': 'JSON',
                        'json': {
                            'data': {
                                'items': {'peer_caller_id_number': 'caller-id'},
                                'notification_type': 'incomingCall',
                            }
                        },
                        'matchType': 'ONLY_MATCHING_FIELDS',
                    },
                },
                'httpResponse': {
                    'statusCode': 200,
                    'body': json.dumps({'message_id': 'message-id-incoming-call'}),
                },
            }
        )
        self.third_party.mock_any_response(
            {
                'httpRequest': {
                    'path': '/fcm/send',
                    'body': {
                        'type': 'JSON',
                        'json': {
                            'data': {
                                'items': {'peer_caller_id_number': 'caller-id'},
                                'notification_type': 'cancelIncomingCall',
                            }
                        },
                        'matchType': 'ONLY_MATCHING_FIELDS',
                    },
                },
                'httpResponse': {
                    'statusCode': 200,
                    'body': json.dumps(
                        {'message_id': 'message-id-cancel-incoming-call'}
                    ),
                },
            }
        )

        self.bus.publish(
            {
                'name': 'auth_user_external_auth_added',
                'origin_uuid': 'my-origin-uuid',
                'data': {'external_auth_name': 'mobile', 'user_uuid': USER_1_UUID},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'auth_user_external_auth_added',
                'origin_uuid': 'my-origin-uuid',
            },
        )

        # webhookd = self.make_webhookd(MASTER_TOKEN)
        self._wait_items(
            functools.partial(self.webhookd.subscriptions.list, recurse=True)
        )
        subscriptions = self.webhookd.subscriptions.list(recurse=True)
        assert_that(subscriptions['total'], equal_to(1))
        assert_that(
            subscriptions['items'][0],
            has_entries(
                name=f"Push notification mobile for user {USERS_TENANT}/{USER_1_UUID}",
                events=contains_inanyorder(
                    'chatd_user_room_message_created',
                    'call_push_notification',
                    'call_cancel_push_notification',
                    'user_voicemail_message_created',
                    'user_missed_call',
                ),
                owner_tenant_uuid=USERS_TENANT,
                owner_user_uuid=USER_1_UUID,
                service='mobile',
            ),
        )

        subscription = subscriptions['items'][0]

        # Send incoming call push notification
        self.bus.publish(
            {
                'name': 'call_push_notification',
                'origin_uuid': 'my-origin-uuid',
                f'user_uuid:{USER_1_UUID}': True,
                'data': {'peer_caller_id_number': 'caller-id'},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'call_push_notification',
                'origin_uuid': 'my-origin-uuid',
                'tenant_uuid': USERS_TENANT,
                f'user_uuid:{USER_1_UUID}': True,
            },
        )

        self._wait_items(
            functools.partial(
                self.webhookd.subscriptions.get_logs, subscription["uuid"]
            )
        )

        logs = self.webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], equal_to(1))
        assert_that(
            logs['items'][0],
            has_entries(
                status="success",
                detail=has_entry(
                    'full_response',
                    has_entry('topic_message_id', 'message-id-incoming-call'),
                ),
                attempts=1,
            ),
        )

        # Canceling the push notification
        self.bus.publish(
            {
                'name': 'call_cancel_push_notification',
                'origin_uuid': 'my-origin-uuid',
                f'user_uuid:{USER_1_UUID}': True,
                'data': {'peer_caller_id_number': 'caller-id'},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'call_push_notification',
                'origin_uuid': 'my-origin-uuid',
                'tenant_uuid': USERS_TENANT,
                f'user_uuid:{USER_1_UUID}': True,
            },
        )

        self._wait_items(
            functools.partial(
                self.webhookd.subscriptions.get_logs, subscription["uuid"]
            ),
            number=2,
        )

        logs = self.webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], equal_to(2))
        assert_that(
            logs['items'][0],
            has_entries(
                status="success",
                detail=has_entry(
                    'full_response',
                    has_entries(topic_message_id='message-id-cancel-incoming-call'),
                ),
                event=has_entries(name='call_cancel_push_notification'),
                attempts=1,
            ),
        )

        self.webhookd.subscriptions.delete(subscription["uuid"])

    def test_missed_call_notification(self):
        # user logs in
        subscription = self._given_mobile_subscription(USER_1_UUID)

        self.third_party.mock_any_response(
            {
                'httpRequest': {
                    'path': '/fcm/send',
                    'headers': {
                        'Content-Type': ['application/json'],
                        'Authorization': ['key=FCM_API_KEY'],
                    },
                },
                'httpResponse': {
                    'statusCode': 200,
                    'body': json.dumps({'message_id': 'message-id-missed-call'}),
                },
            }
        )

        # mobile user misses a call
        self.bus.publish(
            {
                'name': 'user_missed_call',
                'origin_uuid': 'my-origin-uuid',
                'data': {
                    'user_uuid': f'{USER_1_UUID}',
                    'caller_user_uuid': 'ad5b78cf-6e15-45c7-9ef3-bec36e07e8d6',
                    'caller_id_name': 'John Doe',
                    'caller_id_number': '12221114455',
                    'dialed_extension': '8000',
                    'conversation_id': '1718908219.36',
                    'reason': 'no-answer',
                },
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'user_missed_call',
                'origin_uuid': 'my-origin-uuid',
                'tenant_uuid': USERS_TENANT,
                f'user_uuid:{USER_1_UUID}': True,
            },
        )

        def assert_subscription_logs():
            assert self.webhookd.subscriptions.get_logs(subscription["uuid"])

        until.assert_(assert_subscription_logs, timeout=10, interval=0.5)

        # expect FCM API to receive request for push notif
        def assert_fcm_request():
            self.third_party.assert_verify(
                request={
                    'path': '/fcm/send',
                    'headers': [
                        {'name': 'authorization', 'values': ['key=FCM_API_KEY']},
                    ],
                    'body': {
                        'type': 'STRING',
                        'contentType': 'application/json',
                    },
                },
            )

        until.assert_(assert_fcm_request, timeout=10, interval=0.5)

        logs = self.webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], equal_to(1))
        assert_that(
            logs['items'][0],
            has_entries(
                status="success",
                detail=has_entry(
                    'full_response',
                    has_entry('topic_message_id', 'message-id-missed-call'),
                ),
                attempts=1,
            ),
        )

        # check content of FCM request
        fcm_notification_requests = self.third_party.get_requests(path='/fcm/send')
        assert fcm_notification_requests and len(fcm_notification_requests) == 1
        request = fcm_notification_requests[0]

        # expecting a request with a json body and proper authorization header
        assert_that(
            request,
            has_entries(
                body=has_entries(
                    type='STRING',
                    string=instance_of(str),
                    contentType='application/json',
                ),
                headers=has_entries(
                    'Content-Type',
                    contains_exactly('application/json'),
                    'Authorization',
                    contains_exactly('key=FCM_API_KEY'),
                ),
            ),
        )

        # expecting the json body to contain the proper payload
        request_body_json = json.loads(request['body']['string'])

        assert_that(
            request_body_json,
            has_entries(
                notification=has_entries(
                    title=instance_of(str),
                    body=instance_of(str),
                ),
                data=has_entries(
                    items=has_entries(
                        caller_id_name='John Doe',
                        caller_id_number='12221114455',
                    ),
                    notification_type='missedCall',
                ),
            ),
        )


class TestMobileCallbackFCMv1(TestMobileCallback):
    def setUp(self):
        super().setUp()
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

        self.oauth2_token = {
            "access_token": "valid-access-token",
            "scope": "",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        self.auth.set_external_config(
            {
                'mobile': {
                    'fcm_service_account_info': json.dumps(fcm_account_info),
                    'is_sandbox': False,
                }
            }
        )

        self.oauth2_third_party = MockServerClient(
            f'http://127.0.0.1:{self.service_port(443, "oauth2.googleapis.com")}'
        )
        self.oauth2_third_party.reset()
        self.oauth2_third_party.mock_any_response(
            {
                'httpRequest': {
                    'method': 'POST',
                    'path': '/token',
                },
                'httpResponse': {
                    'statusCode': 200,
                    'body': json.dumps(self.oauth2_token),
                },
            }
        )
        self.fcm_third_party = MockServerClient(
            f'http://127.0.0.1:{self.service_port(443, "fcm.googleapis.com")}'
        )
        self.fcm_third_party.reset()

        self.auth.reset_external_auth()
        self.auth.set_external_auth({'token': 'token-android', 'apns_token': None})

    def test_incoming_call_workflow(self):
        self.fcm_third_party.mock_any_response(
            {
                'httpRequest': {
                    'path': '/v1/projects/project-123/messages:send',
                    'body': {
                        'type': 'JSON',
                        'json': {
                            'message': {
                                'data': {
                                    'items': r'"{\"peer_caller_id_number\":\"caller-id\"}"',
                                    'notification_type': 'incomingCall',
                                },
                            },
                        },
                        'matchType': 'ONLY_MATCHING_FIELDS',
                    },
                },
                'httpResponse': {
                    'statusCode': 200,
                    'body': json.dumps({'name': 'message-id-incoming-call'}),
                },
            }
        )
        self.fcm_third_party.mock_any_response(
            {
                'httpRequest': {
                    'path': '/v1/projects/project-123/messages:send',
                    'body': {
                        'type': 'JSON',
                        'json': {
                            'message': {
                                'data': {
                                    'items': r'"{\"peer_caller_id_number\":\"caller-id\"}"',
                                    'notification_type': 'cancelIncomingCall',
                                },
                            },
                        },
                        'matchType': 'ONLY_MATCHING_FIELDS',
                    },
                },
                'httpResponse': {
                    'statusCode': 200,
                    'body': json.dumps({'name': 'message-id-cancel-incoming-call'}),
                },
            }
        )

        self.bus.publish(
            {
                'name': 'auth_user_external_auth_added',
                'origin_uuid': 'my-origin-uuid',
                'data': {'external_auth_name': 'mobile', 'user_uuid': USER_1_UUID},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'auth_user_external_auth_added',
                'origin_uuid': 'my-origin-uuid',
            },
        )

        self._wait_items(
            functools.partial(self.webhookd.subscriptions.list, recurse=True)
        )
        subscriptions = self.webhookd.subscriptions.list(recurse=True)
        assert_that(subscriptions['total'], equal_to(1))
        assert_that(
            subscriptions['items'][0],
            has_entries(
                name=f"Push notification mobile for user {USERS_TENANT}/{USER_1_UUID}",
                events=contains_inanyorder(
                    'chatd_user_room_message_created',
                    'call_push_notification',
                    'call_cancel_push_notification',
                    'user_voicemail_message_created',
                    'user_missed_call',
                ),
                owner_tenant_uuid=USERS_TENANT,
                owner_user_uuid=USER_1_UUID,
                service='mobile',
            ),
        )

        subscription = subscriptions['items'][0]

        # Send incoming call push notification
        self.bus.publish(
            {
                'name': 'call_push_notification',
                'origin_uuid': 'my-origin-uuid',
                f'user_uuid:{USER_1_UUID}': True,
                'data': {'peer_caller_id_number': 'caller-id'},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'call_push_notification',
                'origin_uuid': 'my-origin-uuid',
                'tenant_uuid': USERS_TENANT,
                f'user_uuid:{USER_1_UUID}': True,
            },
        )

        self._wait_items(
            functools.partial(
                self.webhookd.subscriptions.get_logs, subscription["uuid"]
            )
        )

        logs = self.webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], equal_to(1))
        assert_that(
            logs['items'][0],
            has_entries(
                status="success",
                detail=has_entry(
                    'full_response',
                    has_entry('topic_message_id', 'message-id-incoming-call'),
                ),
                attempts=1,
            ),
        )

        # Canceling the push notification
        self.bus.publish(
            {
                'name': 'call_cancel_push_notification',
                'origin_uuid': 'my-origin-uuid',
                f'user_uuid:{USER_1_UUID}': True,
                'data': {'peer_caller_id_number': 'caller-id'},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'call_push_notification',
                'origin_uuid': 'my-origin-uuid',
                'tenant_uuid': USERS_TENANT,
                f'user_uuid:{USER_1_UUID}': True,
            },
        )

        self._wait_items(
            functools.partial(
                self.webhookd.subscriptions.get_logs, subscription["uuid"]
            ),
            number=2,
        )

        logs = self.webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], equal_to(2))
        assert_that(
            logs['items'][0],
            has_entries(
                status="success",
                detail=has_entry(
                    'full_response',
                    has_entries(topic_message_id='message-id-cancel-incoming-call'),
                ),
                event=has_entries(name='call_cancel_push_notification'),
                attempts=1,
            ),
        )

        self.webhookd.subscriptions.delete(subscription["uuid"])

    def test_missed_call_notification(self):
        # user logs in
        subscription = self._given_mobile_subscription(USER_1_UUID)

        self.fcm_third_party.mock_any_response(
            {
                'httpRequest': {
                    'path': '/v1/projects/project-123/messages:send',
                    'headers': {
                        'Content-Type': ['application/json'],
                        'Authorization': [
                            f'Bearer {self.oauth2_token["access_token"]}'
                        ],
                    },
                },
                'httpResponse': {
                    'statusCode': 200,
                    'body': json.dumps({'name': 'message-id-missed-call'}),
                },
            }
        )

        # mobile user misses a call
        self.bus.publish(
            {
                'name': 'user_missed_call',
                'origin_uuid': 'my-origin-uuid',
                'data': {
                    'user_uuid': f'{USER_1_UUID}',
                    'caller_user_uuid': 'ad5b78cf-6e15-45c7-9ef3-bec36e07e8d6',
                    'caller_id_name': 'John Doe',
                    'caller_id_number': '12221114455',
                    'dialed_extension': '8000',
                    'conversation_id': '1718908219.36',
                    'reason': 'no-answer',
                },
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'user_missed_call',
                'origin_uuid': 'my-origin-uuid',
                'tenant_uuid': USERS_TENANT,
                f'user_uuid:{USER_1_UUID}': True,
            },
        )

        def assert_subscription_logs():
            assert self.webhookd.subscriptions.get_logs(subscription["uuid"])

        until.assert_(assert_subscription_logs, timeout=10, interval=0.5)

        # expect FCM API to receive request for push notif
        def assert_fcm_request():
            self.fcm_third_party.assert_verify(
                request={
                    'path': '/v1/projects/project-123/messages:send',
                    'headers': [
                        {
                            'name': 'authorization',
                            'values': [f'Bearer {self.oauth2_token["access_token"]}'],
                        },
                    ],
                    'body': {
                        'type': 'STRING',
                        'contentType': 'application/json',
                    },
                }
            )

        until.assert_(assert_fcm_request, timeout=10, interval=0.5)

        fcm_notification_requests = self.fcm_third_party.get_requests(
            path='/v1/projects/project-123/messages:send'
        )
        assert fcm_notification_requests and len(fcm_notification_requests) == 1
        request = fcm_notification_requests[0]

        # expecting a request with a json body and proper authorization header
        assert_that(
            request,
            has_entries(
                body=has_entries(
                    type='STRING',
                    string=instance_of(str),
                    contentType='application/json',
                ),
                headers=has_entries(
                    'Content-Type',
                    contains_exactly('application/json'),
                    'Authorization',
                    contains_exactly(f'Bearer {self.oauth2_token["access_token"]}'),
                ),
            ),
        )

        # expecting the json body to contain the proper payload
        request_body_json = json.loads(request['body']['string'])

        assert_that(
            request_body_json,
            has_entries(
                message=has_entries(
                    android=has_entries(
                        notification=has_entries(
                            title=instance_of(str),
                            body=instance_of(str),
                        )
                    ),
                    data=has_entries(
                        items=instance_of(str),
                        notification_type='missedCall',
                    ),
                ),
            ),
        )

        logs = self.webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], equal_to(1))
        assert_that(
            logs['items'][0],
            has_entries(
                status="success",
                detail=has_entry(
                    'full_response',
                    has_entry('topic_message_id', 'message-id-missed-call'),
                ),
                attempts=1,
            ),
        )


class TestMobileCallbackAPNS(TestMobileCallback):
    def setUp(self):
        super().setUp()
        self.auth.reset_external_auth()
        self.apns_third_party = MockServerClient(
            f'http://127.0.0.1:{self.service_port(1080, "third-party-http")}'
        )
        self.apns_third_party.reset()
        with open(self.assets_root + "/fake-apple-ca/certs/client.crt") as f:
            ios_apn_certificate = f.read()

        with open(self.assets_root + "/fake-apple-ca/certs/client.key") as f:
            ios_apn_key = f.read()

        self.auth.set_external_config(
            {
                'mobile': {
                    'fcm_api_key': 'FCM_API_KEY',
                    'ios_apn_certificate': ios_apn_certificate,
                    'ios_apn_private': ios_apn_key,
                    'is_sandbox': False,
                }
            }
        )

    def test_workflow_apns_with_app_using_one_token(self):
        # Older iOS apps used only one APNs token
        self.auth.set_external_auth(
            {'token': 'token-android', 'apns_token': 'token-ios'}
        )

        self.apns_third_party.mock_simple_response(
            path='/3/device/token-ios',
            responseBody={'tracker': 'tracker'},
            statusCode=200,
        )
        self.bus.publish(
            {
                'name': 'auth_user_external_auth_added',
                'origin_uuid': 'my-origin-uuid',
                'data': {'external_auth_name': 'mobile', 'user_uuid': USER_2_UUID},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={'name': 'auth_user_external_auth_added'},
        )

        # webhookd = self.make_webhookd(MASTER_TOKEN)
        self._wait_items(
            functools.partial(self.webhookd.subscriptions.list, recurse=True)
        )
        subscriptions = self.webhookd.subscriptions.list(recurse=True)
        assert_that(subscriptions['total'], equal_to(1))
        assert_that(
            subscriptions['items'][0],
            has_entries(
                name=f"Push notification mobile for user {USERS_TENANT}/{USER_2_UUID}",
                events=contains_inanyorder(
                    'chatd_user_room_message_created',
                    'call_push_notification',
                    'call_cancel_push_notification',
                    'user_voicemail_message_created',
                    'user_missed_call',
                ),
                owner_tenant_uuid=USERS_TENANT,
                owner_user_uuid=USER_2_UUID,
                service='mobile',
            ),
        )

        subscription = subscriptions['items'][0]

        # Send incoming call push notification
        self.bus.publish(
            {
                'name': 'call_push_notification',
                'origin_uuid': 'my-origin-uuid',
                f'user_uuid:{USER_2_UUID}': True,
                'data': {'peer_caller_id_number': 'caller-id'},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'call_push_notification',
                'origin_uuid': 'my-origin-uuid',
                'tenant_uuid': USERS_TENANT,
                f'user_uuid:{USER_2_UUID}': True,
            },
        )

        self._wait_items(
            functools.partial(
                self.webhookd.subscriptions.get_logs, subscription["uuid"]
            )
        )

        logs = self.webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], equal_to(1))
        assert_that(
            logs['items'][0],
            has_entries(
                status="success",
                detail=has_entry(
                    'full_response',
                    has_entry('response_body', has_entry('tracker', 'tracker')),
                ),
                attempts=1,
                event=has_entries(name='call_push_notification'),
            ),
        )

        # Send chat message push notification
        self.bus.publish(
            {
                'name': 'chatd_user_room_message_created',
                'origin_uuid': 'my-origin-uuid',
                'data': {'alias': 'sender-name', 'content': 'chat content'},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'chatd_user_room_message_created',
                'origin_uuid': 'my-origin-uuid',
                'tenant_uuid': USERS_TENANT,
                f'user_uuid:{USER_2_UUID}': True,
            },
        )

        self._wait_items(
            functools.partial(
                self.webhookd.subscriptions.get_logs, subscription["uuid"]
            ),
            number=2,
        )

        logs = self.webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], equal_to(2))
        assert_that(
            logs['items'],
            has_item(
                has_entries(
                    status='error',
                    detail=has_entries(
                        message=contains_string('apns_notification_token'),
                        error_id='notification-error',
                    ),
                    attempts=1,
                )
            ),
        )

        self.webhookd.subscriptions.delete(subscription["uuid"])

    def test_workflow_apns_with_app_using_two_tokens(self):
        # self.auth.reset_external_auth()
        # Newer iOS apps use two APNs token
        self.auth.set_external_auth(
            {
                'token': 'token-android',
                'apns_token': 'apns-voip-token',
                'apns_voip_token': 'apns-voip-token',
                'apns_notification_token': 'apns-notification-token',
            }
        )

        self.apns_third_party.mock_simple_response(
            path='/3/device/apns-voip-token',
            responseBody={'tracker': 'tracker-voip'},
            statusCode=200,
        )
        self.apns_third_party.mock_simple_response(
            path='/3/device/apns-notification-token',
            responseBody={'tracker': 'tracker-notification'},
            statusCode=200,
        )
        self.bus.publish(
            {
                'name': 'auth_user_external_auth_added',
                'origin_uuid': 'my-origin-uuid',
                'data': {'external_auth_name': 'mobile', 'user_uuid': USER_2_UUID},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={'name': 'auth_user_external_auth_added'},
        )

        # webhookd = self.make_webhookd(MASTER_TOKEN)
        self._wait_items(
            functools.partial(self.webhookd.subscriptions.list, recurse=True)
        )
        subscriptions = self.webhookd.subscriptions.list(recurse=True)
        assert_that(subscriptions['total'], equal_to(1))
        assert_that(
            subscriptions['items'][0],
            has_entries(
                name=f"Push notification mobile for user {USERS_TENANT}/{USER_2_UUID}",
                events=contains_inanyorder(
                    'chatd_user_room_message_created',
                    'call_push_notification',
                    'call_cancel_push_notification',
                    'user_voicemail_message_created',
                    'user_missed_call',
                ),
                owner_tenant_uuid=USERS_TENANT,
                owner_user_uuid=USER_2_UUID,
                service='mobile',
            ),
        )

        subscription = subscriptions['items'][0]

        # Send incoming call push notification
        self.bus.publish(
            {
                'name': 'call_push_notification',
                'origin_uuid': 'my-origin-uuid',
                f'user_uuid:{USER_2_UUID}': True,
                'data': {'peer_caller_id_number': 'caller-id'},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'call_push_notification',
                'origin_uuid': 'my-origin-uuid',
                'tenant_uuid': USERS_TENANT,
                f'user_uuid:{USER_2_UUID}': True,
            },
        )

        self._wait_items(
            functools.partial(
                self.webhookd.subscriptions.get_logs, subscription["uuid"]
            )
        )

        logs = self.webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], equal_to(1))
        assert_that(
            logs['items'][0],
            has_entries(
                status="success",
                detail=has_entry(
                    'full_response',
                    has_entries(
                        response_body=has_entries(tracker='tracker-voip'),
                    ),
                ),
                event=has_entries(name='call_push_notification'),
                attempts=1,
            ),
        )

        # Canceling the push notification
        self.bus.publish(
            {
                'name': 'call_cancel_push_notification',
                'origin_uuid': 'my-origin-uuid',
                f'user_uuid:{USER_2_UUID}': True,
                'data': {'peer_caller_id_number': 'caller-id'},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'call_push_notification',
                'origin_uuid': 'my-origin-uuid',
                'tenant_uuid': USERS_TENANT,
                f'user_uuid:{USER_2_UUID}': True,
            },
        )

        self._wait_items(
            functools.partial(
                self.webhookd.subscriptions.get_logs, subscription["uuid"]
            ),
            number=2,
        )

        logs = self.webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], equal_to(2))
        assert_that(
            logs['items'][0],
            has_entries(
                status="success",
                detail=has_entry(
                    'full_response',
                    has_entries(
                        response_body=has_entries(tracker='tracker-notification'),
                    ),
                ),
                event=has_entries(name='call_cancel_push_notification'),
                attempts=1,
            ),
        )

        # Send chat message push notification
        self.apns_third_party.reset()
        self.apns_third_party.mock_simple_response(
            path='/3/device/apns-notification-token',
            responseBody={'tracker': 'tracker-notification'},
            statusCode=200,
        )

        self.bus.publish(
            {
                'name': 'chatd_user_room_message_created',
                'origin_uuid': 'my-origin-uuid',
                'data': {'alias': 'sender-name', 'content': 'chat content'},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'chatd_user_room_message_created',
                'origin_uuid': 'my-origin-uuid',
                'tenant_uuid': USERS_TENANT,
                f'user_uuid:{USER_2_UUID}': True,
            },
        )

        self._wait_items(
            functools.partial(
                self.webhookd.subscriptions.get_logs, subscription["uuid"]
            ),
            number=3,
        )

        logs = self.webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], equal_to(3))
        assert_that(
            logs['items'][0],
            has_entries(
                status="success",
                detail=has_entry(
                    'full_response',
                    has_entry(
                        'response_body', has_entry('tracker', 'tracker-notification')
                    ),
                ),
                attempts=1,
            ),
        )

        self.webhookd.subscriptions.delete(subscription["uuid"])

    def test_missed_call_notification(self):
        self.auth.set_external_auth(
            {
                'token': 'token-android',
                'apns_token': 'token-ios',
                'apns_notification_token': 'apns-notification-token',
            }
        )
        # user logs in
        subscription = self._given_mobile_subscription(USER_1_UUID)

        message_uuid = uuid.uuid4()
        self.apns_third_party.mock_simple_response(
            path='/3/device/apns-notification-token',
            responseBody={'tracker': f'tracker-missed-call-{message_uuid}'},
            statusCode=200,
        )

        # mobile user misses a call
        self.bus.publish(
            {
                'name': 'user_missed_call',
                'origin_uuid': 'my-origin-uuid',
                'data': {
                    'user_uuid': f'{USER_1_UUID}',
                    'caller_user_uuid': 'ad5b78cf-6e15-45c7-9ef3-bec36e07e8d6',
                    'caller_id_name': 'A Mctest',
                    'caller_id_number': '8001',
                    'dialed_extension': '8000',
                    'conversation_id': '1718908219.36',
                    'reason': 'no-answer',
                },
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'user_missed_call',
                'origin_uuid': 'my-origin-uuid',
                'tenant_uuid': USERS_TENANT,
                f'user_uuid:{USER_1_UUID}': True,
            },
        )

        def assert_subscription_logs():
            assert self.webhookd.subscriptions.get_logs(subscription["uuid"])

        until.assert_(assert_subscription_logs, timeout=10, interval=0.5)

        def assert_apns_notification_posted():
            try:
                self.apns_third_party.verify(
                    request={
                        'path': '/3/device/apns-notification-token',
                        'headers': [
                            {
                                'name': 'authorization',
                                'values': [f'Bearer {JWT_TENANT_0}'],
                            },
                            {'name': 'user-agent', 'values': ['wazo-webhookd']},
                        ],
                    },
                )
            except Exception:
                raise AssertionError()

        until.assert_(assert_apns_notification_posted, timeout=10, interval=0.5)

        logs = self.webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], equal_to(1))
        print(logs['items'][0])
        assert_that(
            logs['items'][0],
            has_entries(
                status="success",
                detail=has_entry(
                    'full_response',
                    has_entry(
                        'response_body',
                        has_entry('tracker', f'tracker-missed-call-{message_uuid}'),
                    ),
                ),
                attempts=1,
            ),
        )
