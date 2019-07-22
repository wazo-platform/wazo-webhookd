# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
import functools
from hamcrest import assert_that, has_entries, has_entry
import requests
from mockserver import MockServerClient
from xivo_test_helpers import until

from .helpers.base import BaseIntegrationTest
from .helpers.base import MASTER_TOKEN, USER_1_UUID, USERS_TENANT
from .helpers.wait_strategy import ConnectedWaitStrategy

TEST_SUBSCRIPTION = {
    'name': 'test',
    'service': 'mobile',
    'config': {},
    'events_user_uuid': USER_1_UUID,
    'events': ['chatd_user_room_message_created'],
}

TEST_SUBSCRIPTION_WITHOUT_USER_UUID = {
    'name': 'test',
    'service': 'mobile',
    'config': {},
    'events': ['chatd_user_room_message_created'],
}

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
        auth.set_external_config(
            {
                'mobile': {
                    'fcm_api_key': 'FCM_API_KEY',
                    'ios_apn_certificate': 'ios_apn_certificate',
                    'ios_apn_private': 'ios_apn_private',
                    'is_sandbox': False,
                }
            }
        )
        auth.set_external_auth({'token': 'token-android', 'apns_token': None})
        self.third_party = MockServerClient(
            'http://localhost:{port}'.format(
                port=self.service_port(443, 'fcm.googleapis.com')
            )
        )
        self.third_party.reset()
        self.third_party.mock_simple_response(
            path='/fcm/send', responseBody={'message_id': 'message-id'}, statusCode=200
        )

    @staticmethod
    def _wait_items(func, number=1):
        def check():
            logs = func()
            assert_that(logs['total'], number)

        until.assert_(check, tries=10, interval=0.5)

    def test_workflow(self):
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
                owner_tenant_uuid='f0fe8e3a-2d7a-4dd7-8e93-8229d51cfe04',
                owner_user_uuid='b17d9f99-fcc7-4257-8e89-3d0e36e0b48d',
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
