# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import os

import requests

from hamcrest import (
    assert_that,
    is_in,
    not_
)

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

    def setUp(self):
        if self.asset == "base":
            webhookd = self.make_webhookd(VALID_TOKEN)
            subs = webhookd.subscriptions.list()['items']
            for sub in subs:
                subs = webhookd.subscriptions.delete(sub["uuid"])
                self.ensure_webhookd_not_consume_uuid(sub['uuid'])

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

        url = 'https://localhost:{port}/1.0/sentinel'.format(port=self.service_port(9300, 'webhookd'))
        return Sentinel(url)

    def ensure_webhookd_consume_uuid(self, uuid):
        sentinel = self.make_sentinel()
        def subscribed():
            try:
                assert_that(uuid, is_in(sentinel.consumers()))
            except requests.exceptions.ConnectionError:
                raise AssertionError()

        until.assert_(subscribed, tries=10, interval=0.5)

    def ensure_webhookd_not_consume_uuid(self, uuid):
        sentinel = self.make_sentinel()
        def subscribed():
            try:
                assert_that(uuid, not_(is_in(sentinel.consumers())))
            except requests.exceptions.ConnectionError:
                raise AssertionError()

        until.assert_(subscribed, tries=10, interval=0.5)

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
