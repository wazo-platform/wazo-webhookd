# Copyright 2017-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import functools
import json

import requests

from hamcrest import (
    assert_that,
    contains_string,
    contains_inanyorder,
    equal_to,
    has_entries,
    has_entry,
    has_item,
)
from mockserver import MockServerClient
from wazo_test_helpers import until

from .helpers.base import BaseIntegrationTest
from .helpers.base import MASTER_TOKEN, USER_1_UUID, USER_2_UUID, USERS_TENANT
from .helpers.wait_strategy import ConnectedWaitStrategy

SOME_ROUTING_KEY = 'routing-key'


class TestFCMNotificationProxy(BaseIntegrationTest):

    asset = 'proxy'
    wait_strategy = ConnectedWaitStrategy()

    def setUp(self):
        super().setUp()
        self.bus = self.make_bus()
        auth = self.make_auth()
        requests.post(
            auth.url('0.1/users'),
            json={
                'email_address': 'foo@bar',
                'username': 'foobar',
                'password': 'secret',
                'uuid': USER_1_UUID,
            },
            headers={'Wazo-Tenant': USERS_TENANT},
        )
        requests.post(
            auth.url('0.1/users'),
            json={
                'email_address': 'foo@bar',
                'username': 'foobar',
                'password': 'secret',
                'uuid': USER_2_UUID,
            },
            headers={'Wazo-Tenant': USERS_TENANT},
        )

        auth.set_external_config(
            {
                'mobile': {
                    'is_sandbox': False,
                }
            }
        )

    @staticmethod
    def _wait_items(func, number=1):
        def check():
            logs = func()
            assert_that(logs['total'], equal_to(number))

        until.assert_(check, timeout=10, interval=0.5)

    def test_workflow_fcm(self):
        third_party = MockServerClient(
            'http://127.0.0.1:{port}'.format(
                port=self.service_port(443, 'fcm.proxy.example.com')
            )
        )
        third_party.reset()
        third_party.mock_any_response(
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
        third_party.mock_any_response(
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

        auth = self.make_auth()
        auth.reset_external_auth()
        auth.set_external_auth({'token': 'token-android', 'apns_token': None})

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

        webhookd = self.make_webhookd(MASTER_TOKEN)
        self._wait_items(functools.partial(webhookd.subscriptions.list, recurse=True))
        subscriptions = webhookd.subscriptions.list(recurse=True)
        assert_that(subscriptions['total'], equal_to(1))
        assert_that(
            subscriptions['items'][0],
            has_entries(
                name="Push notification mobile for user {}/{}".format(
                    USERS_TENANT, USER_1_UUID
                ),
                events=contains_inanyorder(
                    'chatd_user_room_message_created',
                    'call_push_notification',
                    'call_cancel_push_notification',
                    'user_voicemail_message_created',
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
                'user_uuid:{}'.format(USER_1_UUID): True,
                'data': {'peer_caller_id_number': 'caller-id'},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'call_push_notification',
                'origin_uuid': 'my-origin-uuid',
                'tenant_uuid': USERS_TENANT,
                'user_uuid:{}'.format(USER_1_UUID): True,
            },
        )

        self._wait_items(
            functools.partial(webhookd.subscriptions.get_logs, subscription["uuid"])
        )

        logs = webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], equal_to(1))
        assert_that(
            logs['items'][0],
            has_entries(
                status="success",
                detail=has_entry('topic_message_id', 'message-id-incoming-call'),
                attempts=1,
            ),
        )

        # Canceling the push notification
        self.bus.publish(
            {
                'name': 'call_cancel_push_notification',
                'origin_uuid': 'my-origin-uuid',
                'user_uuid:{}'.format(USER_1_UUID): True,
                'data': {'peer_caller_id_number': 'caller-id'},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'call_push_notification',
                'origin_uuid': 'my-origin-uuid',
                'tenant_uuid': USERS_TENANT,
                'user_uuid:{}'.format(USER_1_UUID): True,
            },
        )

        self._wait_items(
            functools.partial(webhookd.subscriptions.get_logs, subscription["uuid"]),
            number=2,
        )

        logs = webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], equal_to(2))
        assert_that(
            logs['items'][0],
            has_entries(
                status="success",
                detail=has_entries(topic_message_id='message-id-cancel-incoming-call'),
                event=has_entries(name='call_cancel_push_notification'),
                attempts=1,
            ),
        )

        webhookd.subscriptions.delete(subscription["uuid"])


class TestMobileCallback(BaseIntegrationTest):

    asset = 'base'
    wait_strategy = ConnectedWaitStrategy()

    def setUp(self):
        super().setUp()
        self.bus = self.make_bus()
        auth = self.make_auth()
        requests.post(
            auth.url('0.1/users'),
            json={
                'email_address': 'foo@bar',
                'username': 'foobar',
                'password': 'secret',
                'uuid': USER_1_UUID,
            },
            headers={'Wazo-Tenant': USERS_TENANT},
        )
        requests.post(
            auth.url('0.1/users'),
            json={
                'email_address': 'foo@bar',
                'username': 'foobar',
                'password': 'secret',
                'uuid': USER_2_UUID,
            },
            headers={'Wazo-Tenant': USERS_TENANT},
        )

        with open(self.assets_root + "/fake-apple-ca/certs/client.crt") as f:
            ios_apn_certificate = f.read()

        with open(self.assets_root + "/fake-apple-ca/certs/client.key") as f:
            ios_apn_key = f.read()

        auth.set_external_config(
            {
                'mobile': {
                    'fcm_api_key': 'FCM_API_KEY',
                    'ios_apn_certificate': ios_apn_certificate,
                    'ios_apn_private': ios_apn_key,
                    'is_sandbox': False,
                }
            }
        )

    @staticmethod
    def _wait_items(func, number=1):
        def check():
            logs = func()
            assert_that(logs['total'], equal_to(number))

        until.assert_(check, timeout=10, interval=0.5)

    def test_workflow_fcm(self):
        third_party = MockServerClient(
            'http://127.0.0.1:{port}'.format(
                port=self.service_port(443, 'fcm.googleapis.com')
            )
        )
        third_party.reset()
        third_party.mock_any_response(
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
        third_party.mock_any_response(
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

        auth = self.make_auth()
        auth.reset_external_auth()
        auth.set_external_auth({'token': 'token-android', 'apns_token': None})

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

        webhookd = self.make_webhookd(MASTER_TOKEN)
        self._wait_items(functools.partial(webhookd.subscriptions.list, recurse=True))
        subscriptions = webhookd.subscriptions.list(recurse=True)
        assert_that(subscriptions['total'], equal_to(1))
        assert_that(
            subscriptions['items'][0],
            has_entries(
                name="Push notification mobile for user {}/{}".format(
                    USERS_TENANT, USER_1_UUID
                ),
                events=contains_inanyorder(
                    'chatd_user_room_message_created',
                    'call_push_notification',
                    'call_cancel_push_notification',
                    'user_voicemail_message_created',
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
                'user_uuid:{}'.format(USER_1_UUID): True,
                'data': {'peer_caller_id_number': 'caller-id'},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'call_push_notification',
                'origin_uuid': 'my-origin-uuid',
                'tenant_uuid': USERS_TENANT,
                'user_uuid:{}'.format(USER_1_UUID): True,
            },
        )

        self._wait_items(
            functools.partial(webhookd.subscriptions.get_logs, subscription["uuid"])
        )

        logs = webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], equal_to(1))
        assert_that(
            logs['items'][0],
            has_entries(
                status="success",
                detail=has_entry('topic_message_id', 'message-id-incoming-call'),
                attempts=1,
            ),
        )

        # Canceling the push notification
        self.bus.publish(
            {
                'name': 'call_cancel_push_notification',
                'origin_uuid': 'my-origin-uuid',
                'user_uuid:{}'.format(USER_1_UUID): True,
                'data': {'peer_caller_id_number': 'caller-id'},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'call_push_notification',
                'origin_uuid': 'my-origin-uuid',
                'tenant_uuid': USERS_TENANT,
                'user_uuid:{}'.format(USER_1_UUID): True,
            },
        )

        self._wait_items(
            functools.partial(webhookd.subscriptions.get_logs, subscription["uuid"]),
            number=2,
        )

        logs = webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], equal_to(2))
        assert_that(
            logs['items'][0],
            has_entries(
                status="success",
                detail=has_entries(topic_message_id='message-id-cancel-incoming-call'),
                event=has_entries(name='call_cancel_push_notification'),
                attempts=1,
            ),
        )

        webhookd.subscriptions.delete(subscription["uuid"])

    def test_workflow_apns_with_app_using_one_token(self):
        auth = self.make_auth()
        auth.reset_external_auth()
        # Older iOS apps used only one APNs token
        auth.set_external_auth({'token': 'token-android', 'apns_token': 'token-ios'})

        apns_third_party = MockServerClient(
            'http://127.0.0.1:{port}'.format(
                port=self.service_port(1080, 'third-party-http')
            )
        )
        apns_third_party.reset()
        apns_third_party.mock_simple_response(
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

        webhookd = self.make_webhookd(MASTER_TOKEN)
        self._wait_items(functools.partial(webhookd.subscriptions.list, recurse=True))
        subscriptions = webhookd.subscriptions.list(recurse=True)
        assert_that(subscriptions['total'], equal_to(1))
        assert_that(
            subscriptions['items'][0],
            has_entries(
                name="Push notification mobile for user {}/{}".format(
                    USERS_TENANT, USER_2_UUID
                ),
                events=contains_inanyorder(
                    'chatd_user_room_message_created',
                    'call_push_notification',
                    'call_cancel_push_notification',
                    'user_voicemail_message_created',
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
                'user_uuid:{}'.format(USER_2_UUID): True,
                'data': {'peer_caller_id_number': 'caller-id'},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'call_push_notification',
                'origin_uuid': 'my-origin-uuid',
                'tenant_uuid': USERS_TENANT,
                'user_uuid:{}'.format(USER_2_UUID): True,
            },
        )

        self._wait_items(
            functools.partial(webhookd.subscriptions.get_logs, subscription["uuid"])
        )

        logs = webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], equal_to(1))
        assert_that(
            logs['items'][0],
            has_entries(
                status="success",
                detail=has_entry('response_body', has_entry('tracker', 'tracker')),
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
                'user_uuid:{}'.format(USER_2_UUID): True,
            },
        )

        self._wait_items(
            functools.partial(webhookd.subscriptions.get_logs, subscription["uuid"]),
            number=2,
        )

        logs = webhookd.subscriptions.get_logs(subscription["uuid"])
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

        webhookd.subscriptions.delete(subscription["uuid"])

    def test_workflow_apns_with_app_using_two_tokens(self):
        auth = self.make_auth()
        auth.reset_external_auth()
        # Newer iOS apps use two APNs token
        auth.set_external_auth(
            {
                'token': 'token-android',
                'apns_token': 'apns-voip-token',
                'apns_voip_token': 'apns-voip-token',
                'apns_notification_token': 'apns-notification-token',
            }
        )

        apns_third_party = MockServerClient(
            'http://127.0.0.1:{port}'.format(
                port=self.service_port(1080, 'third-party-http')
            )
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
        self.bus.publish(
            {
                'name': 'auth_user_external_auth_added',
                'origin_uuid': 'my-origin-uuid',
                'data': {'external_auth_name': 'mobile', 'user_uuid': USER_2_UUID},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={'name': 'auth_user_external_auth_added'},
        )

        webhookd = self.make_webhookd(MASTER_TOKEN)
        self._wait_items(functools.partial(webhookd.subscriptions.list, recurse=True))
        subscriptions = webhookd.subscriptions.list(recurse=True)
        assert_that(subscriptions['total'], equal_to(1))
        assert_that(
            subscriptions['items'][0],
            has_entries(
                name="Push notification mobile for user {}/{}".format(
                    USERS_TENANT, USER_2_UUID
                ),
                events=contains_inanyorder(
                    'chatd_user_room_message_created',
                    'call_push_notification',
                    'call_cancel_push_notification',
                    'user_voicemail_message_created',
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
                'user_uuid:{}'.format(USER_2_UUID): True,
                'data': {'peer_caller_id_number': 'caller-id'},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'call_push_notification',
                'origin_uuid': 'my-origin-uuid',
                'tenant_uuid': USERS_TENANT,
                'user_uuid:{}'.format(USER_2_UUID): True,
            },
        )

        self._wait_items(
            functools.partial(webhookd.subscriptions.get_logs, subscription["uuid"])
        )

        logs = webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], equal_to(1))
        assert_that(
            logs['items'][0],
            has_entries(
                status="success",
                detail=has_entries(
                    response_body=has_entries(tracker='tracker-voip'),
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
                'user_uuid:{}'.format(USER_2_UUID): True,
                'data': {'peer_caller_id_number': 'caller-id'},
            },
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': 'call_push_notification',
                'origin_uuid': 'my-origin-uuid',
                'tenant_uuid': USERS_TENANT,
                'user_uuid:{}'.format(USER_2_UUID): True,
            },
        )

        self._wait_items(
            functools.partial(webhookd.subscriptions.get_logs, subscription["uuid"]),
            number=2,
        )

        logs = webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], equal_to(2))
        assert_that(
            logs['items'][0],
            has_entries(
                status="success",
                detail=has_entries(
                    response_body=has_entries(tracker='tracker-notification'),
                ),
                event=has_entries(name='call_cancel_push_notification'),
                attempts=1,
            ),
        )

        # Send chat message push notification
        apns_third_party.reset()
        apns_third_party.mock_simple_response(
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
                'user_uuid:{}'.format(USER_2_UUID): True,
            },
        )

        self._wait_items(
            functools.partial(webhookd.subscriptions.get_logs, subscription["uuid"]),
            number=3,
        )

        logs = webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], equal_to(3))
        assert_that(
            logs['items'][0],
            has_entries(
                status="success",
                detail=has_entry(
                    'response_body', has_entry('tracker', 'tracker-notification')
                ),
                attempts=1,
            ),
        )

        webhookd.subscriptions.delete(subscription["uuid"])
