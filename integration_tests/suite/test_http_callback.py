# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from mockserver import MockServerClient
from xivo_test_helpers import until
from xivo_test_helpers.bus import BusClient

from .test_api.base import BaseIntegrationTest
from .test_api.fixtures import subscription

TEST_SUBSCRIPTION = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://third-party-http:1080/test',
               'method': 'get'},
    'events': ['trigger']
}
TEST_SUBSCRIPTION_BODY = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://third-party-http:1080/test',
               'method': 'get',
               'body': '{"body_keỳ": "body_vàlue"}'},
    'events': ['trigger']
}
TEST_SUBSCRIPTION_VERIFY = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'https://third-party-http:1080/test',
               'method': 'get',
               'verify_certificate': 'false'},
    'events': ['trigger']
}
SOME_ROUTING_KEY = 'routing-key'


class TestHTTPCallback(BaseIntegrationTest):

    asset = 'base'

    def make_third_party(self):
        url = 'http://localhost:{port}'.format(port=self.service_port(1080, 'third-party-http'))
        return MockServerClient(url)

    def make_bus(self):
        return BusClient.from_connection_fields(
            host='localhost',
            port=self.service_port(5672, 'rabbitmq')
        )

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_http_subscription_when_bus_event_then_one_http_callback(self, subscription):
        third_party = self.make_third_party()
        bus = self.make_bus()

        # TODO: Delete when /status will be implemented
        import time
        time.sleep(3)

        bus.publish({'name': 'trigger'}, routing_key=SOME_ROUTING_KEY)

        def callback_received():
            try:
                third_party.verify(
                    request={
                        'method': 'GET',
                        'path': '/test',
                        'body': '',
                    }
                )
            except Exception:
                raise AssertionError()

        until.assert_(callback_received, tries=10, interval=0.5)

    @subscription(TEST_SUBSCRIPTION_BODY)
    def test_given_one_http_subscription_with_body_when_bus_event_then_http_callback_with_body(self, subscription):
        third_party = self.make_third_party()
        bus = self.make_bus()

        # TODO: Delete when /status will be implemented
        import time
        time.sleep(3)

        bus.publish({'name': 'trigger'}, routing_key=SOME_ROUTING_KEY)

        def callback_received():
            try:
                third_party.verify(
                    request={
                        'method': 'GET',
                        'path': '/test',
                        'body': '{"body_keỳ": "body_vàlue"}',
                    }
                )
            except Exception:
                raise AssertionError()

        until.assert_(callback_received, tries=10, interval=0.5)

    @subscription(TEST_SUBSCRIPTION_VERIFY)
    def test_given_subscription_with_verify_cert_when_bus_event_then_http_callback_with_verify(self, subscription):
        third_party = self.make_third_party()
        bus = self.make_bus()

        # TODO: Delete when /status will be implemented
        import time
        time.sleep(3)

        bus.publish({'name': 'trigger'}, routing_key=SOME_ROUTING_KEY)

        def callback_received():
            try:
                third_party.verify(
                    request={
                        'method': 'GET',
                        'path': '/test',
                    }
                )
            except Exception:
                raise AssertionError()

        until.assert_(callback_received, tries=10, interval=0.5)
