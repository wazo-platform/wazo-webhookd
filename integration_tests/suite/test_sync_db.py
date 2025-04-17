# Copyright 2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from .helpers.base import (
    MASTER_TENANT,
    MASTER_TOKEN,
    OTHER_TENANT,
    OTHER_USER_UUID,
    USER_1_UUID,
    USER_2_UUID,
    USERS_TENANT,
    WAZO_UUID,
    BaseIntegrationTest,
)
from .helpers.fixtures import subscription
from .helpers.wait_strategy import EverythingOkWaitStrategy

USER_1_TEST_SUBSCRIPTION = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://test.example.com', 'method': 'get'},
    'events': ['test'],
    'owner_user_uuid': USER_1_UUID,
    'events_user_uuid': USER_1_UUID,
    'events_wazo_uuid': WAZO_UUID,
}

USER_2_TEST_SUBSCRIPTION = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://test.example.com', 'method': 'get'},
    'events': ['test'],
    'owner_user_uuid': USER_2_UUID,
    'events_user_uuid': USER_2_UUID,
    'events_wazo_uuid': WAZO_UUID,
}

USER_2_TEST_SUBSCRIPTION_WATCH_USER_1 = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://test.example.com', 'method': 'get'},
    'events': ['test'],
    'owner_user_uuid': USER_2_UUID,
    'events_user_uuid': USER_1_UUID,
    'events_wazo_uuid': WAZO_UUID,
}

OTHER_USER_TEST_SUBSCRIPTION = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://test.example.com', 'method': 'get'},
    'events': ['test'],
    'owner_user_uuid': OTHER_USER_UUID,
    'owner_tenant_uuid': OTHER_TENANT,
    'events_user_uuid': OTHER_USER_UUID,
    'events_wazo_uuid': WAZO_UUID,
}


class TestSyncDB(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = EverythingOkWaitStrategy()

    def setUp(self):
        super().setUp()

    @classmethod
    def sync_db(cls):
        print(cls.docker_exec(['wazo-webhookd-sync-db', '--debug']))

    @subscription(USER_1_TEST_SUBSCRIPTION, tenant=USERS_TENANT, auto_delete=False)
    @subscription(USER_2_TEST_SUBSCRIPTION, tenant=USERS_TENANT)
    @subscription(
        USER_2_TEST_SUBSCRIPTION_WATCH_USER_1, tenant=USERS_TENANT, auto_delete=False
    )
    def test_subscription_auto_delete_on_user_deleted(
        self, subscription_1, subscription_2, subscription_3
    ):
        webhookd = self.make_webhookd(MASTER_TOKEN)
        response = webhookd.subscriptions.list(recurse=True)
        subscription_uuids = {item['uuid'] for item in response['items']}
        assert subscription_1['uuid'] in subscription_uuids
        assert subscription_2['uuid'] in subscription_uuids
        assert subscription_3['uuid'] in subscription_uuids

        auth = self.make_auth()
        # user 1 was deleted
        auth.set_users({'uuid': subscription_2['owner_user_uuid']})

        self.sync_db()

        response = webhookd.subscriptions.list(recurse=True)
        subscription_uuids = {item['uuid'] for item in response['items']}
        assert subscription_1['uuid'] not in subscription_uuids
        assert subscription_2['uuid'] in subscription_uuids
        assert subscription_3['uuid'] not in subscription_uuids

    @subscription(USER_1_TEST_SUBSCRIPTION, tenant=USERS_TENANT)
    @subscription(OTHER_USER_TEST_SUBSCRIPTION, tenant=OTHER_TENANT, auto_delete=False)
    def test_subscription_auto_delete_on_tenant_deleted(
        self, subscription_1, subscription_2
    ):
        webhookd = self.make_webhookd(MASTER_TOKEN)
        response = webhookd.subscriptions.list(recurse=True)
        subscription_uuids = {item['uuid'] for item in response['items']}
        assert subscription_1['uuid'] in subscription_uuids
        assert subscription_2['uuid'] in subscription_uuids

        auth = self.make_auth()
        auth.set_users(
            {'uuid': subscription_1['owner_user_uuid']},
            {'uuid': subscription_2['owner_user_uuid']},
        )
        # other tenant was deleted
        auth.set_tenants(
            {
                'uuid': MASTER_TENANT,
                'name': 'webhookd-tests-master',
                'parent_uuid': MASTER_TENANT,
            },
            {
                'uuid': USERS_TENANT,
                'name': 'webhookd-tests-users',
                'parent_uuid': MASTER_TENANT,
            },
        )

        with auth.capture_requests() as capture:
            self.sync_db()

        assert [{'recurse': 'True'}] == [
            request['query']
            for request in capture.requests
            if request['path'] == '/0.1/users'
        ]
        response = webhookd.subscriptions.list(recurse=True)
        subscription_uuids = {item['uuid'] for item in response['items']}
        assert subscription_1['uuid'] in subscription_uuids
        assert subscription_2['uuid'] not in subscription_uuids
