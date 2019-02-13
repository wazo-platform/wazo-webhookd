# Copyright 2017-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import os

from contextlib import contextmanager
from wazo_webhookd_client import Client as WebhookdClient
from xivo_test_helpers import until
from xivo_test_helpers.asset_launching_test_case import AssetLaunchingTestCase
from xivo_test_helpers.auth import AuthClient
from xivo_test_helpers.bus import BusClient

from .wait_strategy import WaitStrategy

VALID_TOKEN = 'valid-token'


class BaseIntegrationTest(AssetLaunchingTestCase):

    assets_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'assets'))
    service = 'webhookd'
    wait_strategy = WaitStrategy()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        webhookd = cls.make_webhookd(VALID_TOKEN)
        cls.wait_strategy.wait(webhookd)

    @classmethod
    def make_webhookd(cls, token):
        return WebhookdClient('localhost',
                              cls.service_port(9300, 'webhookd'),
                              token=token,
                              verify_certificate=False)

    def make_auth(self):
        return AuthClient('localhost', self.service_port(9497, 'auth'))

    def make_bus(self):
        return BusClient.from_connection_fields(
            host='localhost',
            port=self.service_port(5672, 'rabbitmq')
        )

    @contextmanager
    def auth_stopped(self):
        self.stop_service('auth')
        yield
        self.start_service('auth')
        auth = self.make_auth()
        until.true(auth.is_up, tries=5, message='wazo-auth did not come back up')

    @contextmanager
    def rabbitmq_stopped(self):
        self.stop_service('rabbitmq')
        yield
        self.start_service('rabbitmq')
        bus = self.make_bus()
        until.true(bus.is_up, tries=5, message='rabbitmq did not come back up')
