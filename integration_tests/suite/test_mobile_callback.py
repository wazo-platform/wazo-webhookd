# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
import functools
import json
from hamcrest import assert_that, has_entries, has_entry, has_item
import requests
from mockserver import MockServerClient
from xivo_test_helpers import until

from .helpers.base import BaseIntegrationTest
from .helpers.base import MASTER_TOKEN, USER_1_UUID, USER_2_UUID, USERS_TENANT
from .helpers.wait_strategy import ConnectedWaitStrategy

SOME_ROUTING_KEY = 'routing-key'


class TestMobileCallback(BaseIntegrationTest):

    asset = 'base'
    wait_strategy = ConnectedWaitStrategy()

    def setUp(self):
        super(TestMobileCallback, self).__init__()
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
            verify=False,
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
            verify=False,
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
            assert_that(logs['total'], number)

        until.assert_(check, timeout=10, interval=0.5)

    def test_workflow_fcm(self):
        third_party = MockServerClient(
            'http://localhost:{port}'.format(
                port=self.service_port(443, 'fcm.googleapis.com')
            )
        )
        third_party.reset()
        third_party.mock_any_response({
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
                'body': json.dumps({'message_id': 'message-id-incoming-call'})
            },
        })
        third_party.mock_any_response({
            'httpRequest': {
                'path': '/fcm/send',
                'body': {
                    'type': 'JSON',
                    'json': {
                        'data': {
                            'items': {'call_id': 'some-call-id'},
                            'notification_type': 'callAnswered',
                        }
                    },
                    'matchType': 'ONLY_MATCHING_FIELDS',
                },
            },
            'httpResponse': {
                'statusCode': 200,
                'body': json.dumps({'message_id': 'message-id-call-answered'})
            },
        })
        third_party.mock_any_response({
            'httpRequest': {
                'path': '/fcm/send',
                'body': {
                    'type': 'JSON',
                    'json': {
                        'data': {
                            'items': {'call_id': 'some-call-id'},
                            'notification_type': 'callEnded',
                        }
                    },
                    'matchType': 'ONLY_MATCHING_FIELDS',
                },
            },
            'httpResponse': {
                'statusCode': 200,
                'body': json.dumps({'message_id': 'message-id-call-hungup'})
            },
        })

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
            headers={'name': 'auth_user_external_auth_added'},
        )

        webhookd = self.make_webhookd(MASTER_TOKEN)
        self._wait_items(functools.partial(webhookd.subscriptions.list, recurse=True))
        subscriptions = webhookd.subscriptions.list(recurse=True)
        assert_that(subscriptions['total'], 1)
        assert_that(
            subscriptions['items'][0],
            has_entries(
                name="Push notification mobile for user {}/{}".format(
                    USERS_TENANT, USER_1_UUID
                ),
                events=[
                    'chatd_user_room_message_created',
                    'call_push_notification',
                    'call_updated',
                    'call_ended',
                    'user_voicemail_message_created',
                ],
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
                'user_uuid:{}'.format(USER_1_UUID): True,
            },
        )

        self._wait_items(
            functools.partial(webhookd.subscriptions.get_logs, subscription["uuid"])
        )

        logs = webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], 1)
        assert_that(
            logs['items'][0],
            has_entries(
                status="success",
                detail=has_entry('topic_message_id', 'message-id-incoming-call'),
                attempts=1,
            ),
        )

        # Send call answered elsewhere push notification
        self.bus.publish(
            {
                'name': 'call_updated',
                'origin_uuid': 'my-origin-uuid',
                'user_uuid:{}'.format(USER_1_UUID): True,
                'data': {
                    'call_id': 'some-call-id',
                    'status': 'Up',
                    'is_caller': False,
                    'peer_caller_id_number': 'caller-id',
                },
            },
            routing_key=SOME_ROUTING_KEY,
            headers={'name': 'call_updated', 'user_uuid:{}'.format(USER_1_UUID): True},
        )

        self._wait_items(
            functools.partial(webhookd.subscriptions.get_logs, subscription["uuid"])
        )

        def call_updated_push_notification_sent():
            logs = webhookd.subscriptions.get_logs(subscription["uuid"])
            assert_that(
                logs['items'],
                has_item(
                    has_entries(
                        status="success",
                        detail=has_entry(
                            'topic_message_id', 'message-id-call-answered'
                        ),
                        attempts=1,
                    )
                ),
            )

        until.assert_(call_updated_push_notification_sent, timeout=10, interval=0.5)

        # Send call hungup push notification
        self.bus.publish(
            {
                'name': 'call_ended',
                'origin_uuid': 'my-origin-uuid',
                'user_uuid:{}'.format(USER_1_UUID): True,
                'data': {
                    'call_id': 'some-call-id',
                    'peer_caller_id_number': 'caller-id'
                },
            },
            routing_key=SOME_ROUTING_KEY,
            headers={'name': 'call_ended', 'user_uuid:{}'.format(USER_1_UUID): True},
        )

        self._wait_items(
            functools.partial(webhookd.subscriptions.get_logs, subscription["uuid"])
        )

        def call_ended_push_notification_sent():
            logs = webhookd.subscriptions.get_logs(subscription["uuid"])
            assert_that(
                logs['items'],
                has_item(
                    has_entries(
                        status="success",
                        detail=has_entry('topic_message_id', 'message-id-call-hungup'),
                        attempts=1,
                    )
                ),
            )

        until.assert_(call_updated_push_notification_sent, timeout=10, interval=0.5)

        webhookd.subscriptions.delete(subscription["uuid"])

    def test_workflow_apns(self):
        auth = self.make_auth()
        auth.reset_external_auth()
        auth.set_external_auth({'token': 'token-android', 'apns_token': 'token-ios'})

        apns_third_party = MockServerClient(
            'http://localhost:{port}'.format(
                port=self.service_port(1080, 'third-party-http')
            )
        )
        fcm_third_party = MockServerClient(
            'http://localhost:{port}'.format(
                port=self.service_port(443, 'fcm.googleapis.com')
            )
        )
        apns_third_party.reset()
        apns_third_party.mock_simple_response(
            path='/3/device/token-ios',
            responseBody={'tracker': 'tracker'},
            statusCode=200,
        )
        fcm_third_party.reset()
        fcm_third_party.mock_any_response({
            'httpRequest': {
                'path': '/fcm/send',
                'body': {
                    'type': 'JSON',
                    'json': {
                        'data': {
                            'items': {'call_id': 'some-call-id'},
                            'notification_type': 'callAnswered',
                        }
                    },
                    'matchType': 'ONLY_MATCHING_FIELDS',
                },
            },
            'httpResponse': {
                'statusCode': 200,
                'body': json.dumps({'message_id': 'message-id-call-answered'})
            },
        })
        fcm_third_party.mock_any_response({
            'httpRequest': {
                'path': '/fcm/send',
                'body': {
                    'type': 'JSON',
                    'json': {
                        'data': {
                            'items': {'call_id': 'some-call-id'},
                            'notification_type': 'callEnded',
                        }
                    },
                    'matchType': 'ONLY_MATCHING_FIELDS',
                },
            },
            'httpResponse': {
                'statusCode': 200,
                'body': json.dumps({'message_id': 'message-id-call-hungup'})
            },
        })

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
        assert_that(subscriptions['total'], 1)
        assert_that(
            subscriptions['items'][0],
            has_entries(
                name="Push notification mobile for user {}/{}".format(
                    USERS_TENANT, USER_2_UUID
                ),
                events=[
                    'chatd_user_room_message_created',
                    'call_push_notification',
                    'call_updated',
                    'call_ended',
                    'user_voicemail_message_created',
                ],
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
                'user_uuid:{}'.format(USER_2_UUID): True,
            },
        )

        self._wait_items(
            functools.partial(webhookd.subscriptions.get_logs, subscription["uuid"])
        )

        logs = webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], 1)
        assert_that(
            logs['items'][0],
            has_entries(
                status="success",
                detail=has_entry('response_body', has_entry('tracker', 'tracker')),
                attempts=1,
            ),
        )

        # Send call answered elsewhere push notification
        self.bus.publish(
            {
                'name': 'call_updated',
                'origin_uuid': 'my-origin-uuid',
                'user_uuid:{}'.format(USER_2_UUID): True,
                'data': {
                    'call_id': 'some-call-id',
                    'status': 'Up',
                    'is_caller': False,
                    'peer_caller_id_number': 'caller-id',
                },
            },
            routing_key=SOME_ROUTING_KEY,
            headers={'name': 'call_updated', 'user_uuid:{}'.format(USER_2_UUID): True},
        )

        self._wait_items(
            functools.partial(webhookd.subscriptions.get_logs, subscription["uuid"])
        )

        def call_updated_push_notification_sent():
            logs = webhookd.subscriptions.get_logs(subscription["uuid"])
            assert_that(
                logs['items'],
                has_item(
                    has_entries(
                        status="success",
                        detail=has_entry(
                            'topic_message_id', 'message-id-call-answered'
                        ),
                        attempts=1,
                    )
                ),
            )

        until.assert_(call_updated_push_notification_sent, timeout=10, interval=0.5)

        # Send call hungup push notification
        self.bus.publish(
            {
                'name': 'call_ended',
                'origin_uuid': 'my-origin-uuid',
                'user_uuid:{}'.format(USER_2_UUID): True,
                'data': {
                    'call_id': 'some-call-id',
                    'peer_caller_id_number': 'caller-id'
                },
            },
            routing_key=SOME_ROUTING_KEY,
            headers={'name': 'call_ended', 'user_uuid:{}'.format(USER_2_UUID): True},
        )

        self._wait_items(
            functools.partial(webhookd.subscriptions.get_logs, subscription["uuid"])
        )

        def call_ended_push_notification_sent():
            logs = webhookd.subscriptions.get_logs(subscription["uuid"])
            assert_that(
                logs['items'],
                has_item(
                    has_entries(
                        status="success",
                        detail=has_entry('topic_message_id', 'message-id-call-hungup'),
                        attempts=1,
                    )
                ),
            )

        until.assert_(call_updated_push_notification_sent, timeout=10, interval=0.5)

        webhookd.subscriptions.delete(subscription["uuid"])
