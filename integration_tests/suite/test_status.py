# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import assert_that
from hamcrest import equal_to
from hamcrest import has_entries
from xivo_test_helpers import until

from .helpers.base import BaseIntegrationTest
from .helpers.base import VALID_TOKEN
from .helpers.wait_strategy import NoWaitStrategy


class TestStatusRabbitMQStops(BaseIntegrationTest):

    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def test_given_rabbitmq_stops_when_status_then_bus_consumer_status_fail(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        def all_connections_ok():
            result = webhookd.status.get()
            assert_that(result['connections'], has_entries({'bus_consumer': 'ok'}))

        until.assert_(all_connections_ok, tries=5)

        def rabbitmq_is_down():
            result = webhookd.status.get()
            assert_that(result['connections']['bus_consumer'], equal_to('fail'))

        with self.rabbitmq_stopped():
            until.assert_(rabbitmq_is_down, tries=5)


class TestStatusAllOK(BaseIntegrationTest):

    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def test_given_rabbitmq_when_status_then_status_ok(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        def all_connections_ok():
            result = webhookd.status.get()
            assert_that(result['connections'], has_entries({'bus_consumer': 'ok'}))

        until.assert_(all_connections_ok, tries=10)
