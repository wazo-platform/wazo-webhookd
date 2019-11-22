# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import os

import requests

from hamcrest import assert_that, is_in, not_

from contextlib import contextmanager
from wazo_webhookd_client import Client as WebhookdClient
from xivo.config_helper import parse_config_file
from xivo_test_helpers import until
from xivo_test_helpers.auth import MockCredentials, MockUserToken
from xivo_test_helpers.asset_launching_test_case import AssetLaunchingTestCase
from xivo_test_helpers.auth import AuthClient
from xivo_test_helpers.bus import BusClient

from .wait_strategy import WaitStrategy

VALID_TOKEN = "valid-token"

WAZO_UUID = '613747fd-f7e7-4329-b115-3869e44a05d2'

MASTER_TENANT = '4eb57648-b914-446b-a69f-58643ae08dd4'
MASTER_USER_UUID = '5b6e5030-0f23-499a-8030-4a390392aad2'
MASTER_TOKEN = 'cfe6dd71-5d0e-41c8-9178-0ce6578b5a71'

USERS_TENANT = 'f0fe8e3a-2d7a-4dd7-8e93-8229d51cfe04'
USER_1_UUID = 'b17d9f99-fcc7-4257-8e89-3d0e36e0b48d'
USER_1_TOKEN = '756b980b-1cab-4048-933e-f3564ac1f5fc'
USER_2_UUID = 'f79fd307-467c-4851-b614-e65bc8d922fc'
USER_2_TOKEN = 'df8b0b7e-2621-4244-87f8-e85d27fe3955'

OTHER_TENANT = '0a5afd22-6325-49b1-8e35-b04618e78b58'
OTHER_USER_UUID = '35faa8d3-3d89-4a72-b897-0706125c7a35'
OTHER_USER_TOKEN = '2c369402-fa85-4ea5-84ed-933cbd1002f0'


class BaseIntegrationTest(AssetLaunchingTestCase):

    assets_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'assets')
    )
    service = 'webhookd'
    wait_strategy = WaitStrategy()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        webhookd = cls.make_webhookd(VALID_TOKEN)
        cls.wait_strategy.wait(webhookd)
        if cls.asset == "base":
            cls.configured_wazo_auth()
            cls.docker_exec(['wazo-webhookd-init-amqp', '--host', 'rabbitmq'])

    def setUp(self):
        if self.asset == "base":
            webhookd = self.make_webhookd(MASTER_TOKEN)
            subs = webhookd.subscriptions.list(recurse=True)['items']
            for sub in subs:
                webhookd = self.make_webhookd(
                    MASTER_TOKEN, tenant=sub["owner_tenant_uuid"]
                )
                webhookd.subscriptions.delete(sub["uuid"])
                self.ensure_webhookd_not_consume_uuid(sub['uuid'])

    @classmethod
    def make_webhookd(cls, token, tenant=None):
        return WebhookdClient(
            'localhost',
            cls.service_port(9300, 'webhookd'),
            token=token,
            tenant=tenant,
            verify_certificate=False,
        )

    @classmethod
    def make_auth(cls):
        return AuthClient('localhost', cls.service_port(9497, 'auth'))

    @classmethod
    def configured_wazo_auth(cls):
        # NOTE(sileht): This creates a tenant tree and associated users
        key_file = parse_config_file(
            os.path.join(cls.assets_root, "keys", "wazo-webhookd-key.yml")
        )
        auth = cls.make_auth()
        auth.set_valid_credentials(
            MockCredentials(key_file['service_id'], key_file['service_key']),
            MASTER_TOKEN,
        )
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
            host='localhost', port=self.service_port(5672, 'rabbitmq')
        )

    def make_sentinel(self):
        class Sentinel:
            def __init__(self, url):
                self._url = url

            def consumers(self):
                response = requests.get(self._url, verify=False)
                response.raise_for_status()
                return response.json()['consumers']

            def called(self):
                response = requests.get(self._url, verify=False)
                response.raise_for_status()
                return response.json()['called']

            def reset(self):
                requests.delete(self._url, verify=False)

        url = 'https://localhost:{port}/1.0/sentinel'.format(
            port=self.service_port(9300, 'webhookd')
        )
        return Sentinel(url)

    def ensure_webhookd_consume_uuid(self, uuid):
        sentinel = self.make_sentinel()

        def subscribed():
            try:
                assert_that(uuid, is_in(sentinel.consumers()))
            except requests.exceptions.ConnectionError:
                raise AssertionError()

        until.assert_(subscribed, timeout=10, interval=0.5)

    def ensure_webhookd_not_consume_uuid(self, uuid):
        sentinel = self.make_sentinel()

        def subscribed():
            try:
                assert_that(uuid, not_(is_in(sentinel.consumers())))
            except requests.exceptions.ConnectionError:
                raise AssertionError()

        until.assert_(subscribed, timeout=10, interval=0.5)

    @contextmanager
    def auth_stopped(self):
        self.stop_service('auth')
        yield
        self.start_service('auth')
        auth = self.make_auth()
        until.true(auth.is_up, timeout=5, message='wazo-auth did not come back up')
        self.configured_wazo_auth()

    @contextmanager
    def rabbitmq_stopped(self):
        self.stop_service('rabbitmq')
        yield
        self.start_service('rabbitmq')
        bus = self.make_bus()
        until.true(bus.is_up, timeout=5, message='rabbitmq did not come back up')
