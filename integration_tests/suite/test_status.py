# Copyright 2017-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that
from hamcrest import equal_to
from hamcrest import has_entries
from xivo_test_helpers import until

from .helpers.base import BaseIntegrationTest
from .helpers.base import MASTER_TOKEN
from .helpers.wait_strategy import NoWaitStrategy


class TestStatusRabbitMQStops(BaseIntegrationTest):

    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def test_given_rabbitmq_stops_when_status_then_bus_consumer_status_fail(self):
        webhookd = self.make_webhookd(MASTER_TOKEN)

        def all_connections_ok():
            result = webhookd.status.get()
            assert_that(result['bus_consumer'], has_entries({'status': 'ok'}))

        until.assert_(all_connections_ok, timeout=20)

        def rabbitmq_is_down():
            result = webhookd.status.get()
            assert_that(result['bus_consumer']['status'], equal_to('fail'))

        with self.rabbitmq_stopped():
            until.assert_(rabbitmq_is_down, timeout=10)


class TestStatusAllOK(BaseIntegrationTest):

    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def test_given_rabbitmq_when_status_then_status_ok(self):
        webhookd = self.make_webhookd(MASTER_TOKEN)

        def all_connections_ok():
            result = webhookd.status.get()
            assert_that(
                result,
                has_entries(
                    bus_consumer=has_entries(status='ok'),
                    master_tenant=has_entries(status='ok'),
                ),
            )

        until.assert_(all_connections_ok, timeout=20)


class TestStatusNoMasterTenant(BaseException):
    def test_before_master_tenant_initialization(self):
        self.stop_service('webhookd')
        self.stop_service('auth')
        self.start_service('webhookd')

        webhookd = self.make_webhookd(MASTER_TOKEN)

        def master_tenant_is_not_set():
            result = webhookd.status.get()
            assert_that(
                result,
                has_entries(
                    master_tenant=has_entries(status='fail'),
                ),
            )

        until.assert_(master_tenant_is_not_set, timeout=10)

        self.start_service('auth')

        def master_tenant_ok():
            result = webhookd.status.get()
            assert_that(
                result,
                has_entries(
                    master_tenant=has_entries(status='ok'),
                ),
            )

        until.assert_(master_tenant_ok, timeout=20)
