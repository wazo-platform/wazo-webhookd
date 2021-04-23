# Copyright 2020-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that, equal_to
from xivo_test_helpers.bus import BusClient
from xivo_test_helpers import until

from .helpers.base import BaseIntegrationTest
from .helpers.wait_strategy import ConnectedWaitStrategy


class TestBusConsumer(BaseIntegrationTest):

    asset = 'base'
    wait_strategy = ConnectedWaitStrategy()

    def setUp(self):
        super().setUp()
        bus_port = self.service_port(5672, 'rabbitmq')
        self.bus = BusClient.from_connection_fields(host='127.0.0.1', port=bus_port)

    def test_message_is_received(self):
        ping_event = {'name': 'webhookd_ping', 'data': {'payload': 'test-ping'}}

        self.bus.publish(ping_event, headers={'name': 'webhookd_ping'})

        until.assert_(self._ping_bus_event_received, 'test-ping', tries=5)

    def test_message_is_received_after_error(self):
        crash_event = {'name': 'crash_ping', 'data': {}}
        self.bus.publish(crash_event, headers={'name': 'crash_ping'})

        ping_event = {'name': 'webhookd_ping', 'data': {'payload': 'test-crash-ping'}}
        self.bus.publish(ping_event, headers={'name': 'webhookd_ping'})

        until.assert_(self._ping_bus_event_received, 'test-crash-ping', tries=5)

    def _ping_bus_event_received(self, expected_payload):
        webhookd = self.make_webhookd(token=None)
        response = webhookd.sentinel_bus.get()
        assert_that(response['last_event_payload'], equal_to(expected_payload))
