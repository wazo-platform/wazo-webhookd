# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
import functools
from hamcrest import assert_that, has_entries, has_entry
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

        until.assert_(check, tries=10, interval=0.5)

    def test_workflow_fcm(self):
        third_party = MockServerClient(
            'http://localhost:{port}'.format(
                port=self.service_port(443, 'fcm.googleapis.com')
            )
        )
        third_party.reset()
        third_party.mock_simple_response(
            path='/fcm/send', responseBody={'message_id': 'message-id'}, statusCode=200
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
                    'user_voicemail_message_created',
                ],
                owner_tenant_uuid=USERS_TENANT,
                owner_user_uuid=USER_1_UUID,
                service='mobile',
            ),
        )

        subscription = subscriptions['items'][0]

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
                detail=has_entry('topic_message_id', 'message-id'),
                attempts=1,
            ),
        )
        webhookd.subscriptions.delete(subscription["uuid"])

    def test_workflow_apns(self):
        auth = self.make_auth()
        auth.reset_external_auth()
        auth.set_external_auth({'token': None, 'apns_token': 'token-ios'})

        third_party = MockServerClient(
            'http://localhost:{port}'.format(
                port=self.service_port(1080, 'third-party-http')
            )
        )
        third_party.reset()
        third_party.mock_simple_response(
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
                    'user_voicemail_message_created',
                ],
                owner_tenant_uuid=USERS_TENANT,
                owner_user_uuid=USER_2_UUID,
                service='mobile',
            ),
        )

        subscription = subscriptions['items'][0]

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
        webhookd.subscriptions.delete(subscription["uuid"])
