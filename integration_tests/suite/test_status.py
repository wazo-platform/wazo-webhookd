# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import assert_that
from hamcrest import equal_to
from hamcrest import has_entries
from xivo_test_helpers import until

from .test_api.base import BaseIntegrationTest
from .test_api.base import VALID_TOKEN


class TestStatusRabbitMQStops(BaseIntegrationTest):

    asset = 'base'

    def test_given_rabbitmq_stops_when_status_then_bus_consumer_status_fail(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        def all_connections_ok():
            result = webhookd.status.get()
            assert_that(result['connections'], has_entries({'bus_consumer': 'ok'}))

        until.assert_(all_connections_ok, tries=5)

        self.stop_service('rabbitmq')

        def rabbitmq_is_down():
            result = webhookd.status.get()
            assert_that(result['connections']['bus_consumer'], equal_to('fail'))

        until.assert_(rabbitmq_is_down, tries=5)


class TestStatusAllOK(BaseIntegrationTest):

    asset = 'base'

    def test_given_rabbitmq_when_status_then_status_ok(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        def all_connections_ok():
            result = webhookd.status.get()
            assert_that(result['connections'], has_entries({'bus_consumer': 'ok'}))

        until.assert_(all_connections_ok, tries=10)
