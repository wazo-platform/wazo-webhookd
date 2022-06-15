# Copyright 2017-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import requests

from contextlib import contextmanager
from wazo_webhookd_client import Client as WebhookdClient
from wazo_test_helpers import until
from wazo_test_helpers.auth import MockCredentials, MockUserToken
from wazo_test_helpers.asset_launching_test_case import AssetLaunchingTestCase
from wazo_test_helpers.auth import AuthClient
from wazo_test_helpers.bus import BusClient

from .wait_strategy import WaitStrategy

WAZO_UUID = '00000000-0000-4000-8000-00003eb8004d'

MASTER_TOKEN = '00000000-0000-4000-8000-000000000101'
MASTER_TENANT = '00000000-0000-4000-8000-000000000201'
MASTER_USER_UUID = '00000000-0000-4000-8000-000000000301'

USERS_TENANT = '00000000-0000-4000-8000-000000000202'
USER_1_UUID = '00000000-0000-4000-8000-000000000302'
USER_1_TOKEN = '00000000-0000-4000-8000-000000000102'
USER_2_UUID = '00000000-0000-4000-8000-000000000303'
USER_2_TOKEN = '00000000-0000-4000-8000-000000000103'

OTHER_TENANT = '00000000-0000-4000-8000-000000000204'
OTHER_USER_UUID = '00000000-0000-4000-8000-000000000304'
OTHER_USER_TOKEN = '00000000-0000-4000-8000-000000000204'

START_TIMEOUT = int(os.environ.get('INTEGRATION_TEST_TIMEOUT', '30'))


class BaseIntegrationTest(AssetLaunchingTestCase):

    assets_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'assets')
    )
    service = 'webhookd'
    wait_strategy = WaitStrategy()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        webhookd = cls.make_webhookd(MASTER_TOKEN)
        if cls.asset == "base":
            cls.configured_wazo_auth()
            cls.docker_exec(['wazo-webhookd-init-amqp', '--host', 'rabbitmq'])
        cls.wait_strategy.wait(webhookd)

    def setUp(self):
        if self.asset == "base":
            webhookd = self.make_webhookd(MASTER_TOKEN)
            subs = webhookd.subscriptions.list(recurse=True)['items']
            for sub in subs:
                webhookd = self.make_webhookd(
                    MASTER_TOKEN, tenant=sub["owner_tenant_uuid"]
                )
                webhookd.subscriptions.delete(sub["uuid"])
                self.ensure_webhookd_not_consume_subscription(sub)

    @classmethod
    def make_webhookd(cls, token, tenant=None, **kwargs):
        return WebhookdClient(
            '127.0.0.1',
            cls.service_port(9300, 'webhookd'),
            prefix=None,
            https=False,
            token=token,
            tenant=tenant,
            **kwargs
        )

    @classmethod
    def make_auth(cls):
        return AuthClient('127.0.0.1', cls.service_port(9497, 'auth'))

    @classmethod
    def configured_wazo_auth(cls):
        auth = cls.make_auth()
        credential = MockCredentials('webhookd-service', 'webhookd-password')
        auth.set_valid_credentials(credential, MASTER_TOKEN)
        auth.set_token(
            MockUserToken(
                MASTER_TOKEN,
                MASTER_USER_UUID,
                WAZO_UUID,
                {"tenant_uuid": MASTER_TENANT, "uuid": MASTER_USER_UUID},
            )
        )
        auth.set_token(
            MockUserToken(
                USER_1_TOKEN,
                USER_1_UUID,
                WAZO_UUID,
                {"tenant_uuid": USERS_TENANT, "uuid": USER_1_UUID},
            )
        )
        auth.set_token(
            MockUserToken(
                USER_2_TOKEN,
                USER_2_UUID,
                WAZO_UUID,
                {"tenant_uuid": USERS_TENANT, "uuid": USER_2_UUID},
            )
        )
        auth.set_token(
            MockUserToken(
                OTHER_USER_TOKEN,
                OTHER_USER_UUID,
                WAZO_UUID,
                {"tenant_uuid": OTHER_TENANT, "uuid": OTHER_USER_UUID},
            )
        )
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
            {
                'uuid': OTHER_TENANT,
                'name': 'webhookd-tests-other',
                'parent_uuid': MASTER_TENANT,
            },
        )

    def make_bus(self):
        return BusClient.from_connection_fields(
            host='127.0.0.1', port=self.service_port(5672, 'rabbitmq')
        )

    def make_sentinel(self):
        class Sentinel:
            def __init__(self, url):
                self._url = url

            def bindings(self):
                response = requests.get(self._url, verify=False)
                response.raise_for_status()
                return response.json()['bindings']

            def called(self):
                response = requests.get(self._url, verify=False)
                response.raise_for_status()
                return response.json()['called']

            def reset(self):
                requests.delete(self._url, verify=False)

        url = 'http://127.0.0.1:{port}/1.0/sentinel'.format(
            port=self.service_port(9300, 'webhookd')
        )
        return Sentinel(url)

    def _has_subscription_bindings(self, subscription, bindings):
        events_count = len(subscription['events'])
        bindings_count = len(
            [binding for binding in bindings if binding['uuid'] == subscription['uuid']]
        )
        return bindings_count == events_count

    def ensure_webhookd_consume_subscription(self, subscription):
        sentinel = self.make_sentinel()

        def subscribed():
            try:
                bindings = sentinel.bindings()
            except requests.exceptions.ConnectionError:
                raise AssertionError()

            return self._has_subscription_bindings(subscription, bindings)

        until.true(subscribed, timeout=10, interval=0.5)

    def ensure_webhookd_not_consume_subscription(self, subscription):
        sentinel = self.make_sentinel()

        def subscribed():
            try:
                bindings = sentinel.bindings()
            except requests.exceptions.ConnectionError:
                raise AssertionError()

            return self._has_subscription_bindings(subscription, bindings)

        until.false(subscribed, timeout=10, interval=0.5)

    @contextmanager
    def auth_stopped(self):
        self.stop_service('auth')
        yield
        self.start_service('auth')
        auth = self.make_auth()
        until.true(
            auth.is_up, timeout=START_TIMEOUT, message='wazo-auth did not come back up'
        )
        self.configured_wazo_auth()

    @contextmanager
    def rabbitmq_stopped(self):
        self.stop_service('rabbitmq')
        yield
        self.start_service('rabbitmq')
        bus = self.make_bus()
        until.true(
            bus.is_up, timeout=START_TIMEOUT, message='rabbitmq did not come back up'
        )
