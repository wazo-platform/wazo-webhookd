# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import requests
import time

from mockserver import MockServerClient
from xivo_test_helpers import until

from .test_api.base import BaseIntegrationTest
from .test_api.base import VALID_TOKEN
from .test_api.fixtures import subscription
from .test_api.wait_strategy import ConnectedWaitStrategy

ALICE_USER_UUID = '19f216be-916c-415c-83b5-6a13af92dd86'
ALICE_USER_UUID_EXTENDED = '19f216be-916c-415c-83b5-6a13af92dd86-suffix'
BOB_USER_UUID = '19f216be-916c-415c-83b5-6a13af92dd87'
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
TEST_SUBSCRIPTION_URL_TEMPLATE = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://third-party-http:1080/test/{{ event["variable"] }}?{{ event|urlencode }}',
               'method': 'get'},
    'events': ['trigger']
}
TEST_SUBSCRIPTION_BODY_TEMPLATE = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://third-party-http:1080/test',
               'method': 'get',
               'body': '{{ event_name }} {{ event["variable"] }}'},
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
TEST_SUBSCRIPTION_CONTENT_TYPE = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://third-party-http:1080/test',
               'method': 'post',
               'body': 'keỳ: vàlue',
               'content_type': 'text/yaml'},
    'events': ['trigger']
}
TEST_SUBSCRIPTION_NO_TRIGGER = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://third-party-http:1080/test',
               'method': 'get'},
    'events': ['dont-trigger']
}
TEST_SUBSCRIPTION_FILTER_USER_ALICE = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://third-party-http:1080/test',
               'method': 'get'},
    'events': ['trigger'],
    'events_user_uuid': ALICE_USER_UUID,
}
SOME_ROUTING_KEY = 'routing-key'
TRIGGER_EVENT_NAME = 'trigger'
ANOTHER_TRIGGER_EVENT_NAME = 'another-trigger'
DONT_TRIGGER_EVENT_NAME = 'dont-trigger'
STILL_DONT_TRIGGER_EVENT_NAME = 'still-dont-trigger'


def trigger_event(**kwargs):
    return event(name=TRIGGER_EVENT_NAME, **kwargs)


def event(**kwargs):
    kwargs.setdefault('name', 'my-event-name')
    kwargs.setdefault('data', {})
    kwargs.setdefault('origin_uuid', 'my-origin-uuid')
    return kwargs


class TestHTTPCallback(BaseIntegrationTest):

    asset = 'base'
    wait_strategy = ConnectedWaitStrategy()

    def make_third_party(self):
        url = 'http://localhost:{port}'.format(port=self.service_port(1080, 'third-party-http'))
        return MockServerClient(url)

    def make_sentinel(self):
        class Sentinel:
            def __init__(self, url):
                self._url = url

            def called(self):
                response = requests.get(self._url, verify=False)
                response.raise_for_status()
                return response.json()['called']

        url = 'https://localhost:{port}/1.0/sentinel'.format(port=self.service_port(9300, 'webhookd'))
        return Sentinel(url)

    def setUp(self):
        third_party = self.make_third_party()
        third_party.reset()

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_http_subscription_when_bus_event_then_one_http_callback(self, subscription):
        third_party = self.make_third_party()
        bus = self.make_bus()

        bus.publish(trigger_event(),
                    routing_key=SOME_ROUTING_KEY,
                    headers={'name': TRIGGER_EVENT_NAME})

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

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_http_subscription_when_update_events_then_callback_triggered_on_the_right_event(self, subscription):
        bus = self.make_bus()
        third_party = self.make_third_party()
        webhookd = self.make_webhookd(VALID_TOKEN)
        old_trigger_name = TRIGGER_EVENT_NAME

        subscription['events'] = [ANOTHER_TRIGGER_EVENT_NAME]
        webhookd.subscriptions.update(subscription['uuid'], subscription)
        time.sleep(1)  # wait for the subscription to be updated

        bus.publish(event(name=old_trigger_name),
                    routing_key=SOME_ROUTING_KEY,
                    headers={'name': old_trigger_name})
        bus.publish(event(name=ANOTHER_TRIGGER_EVENT_NAME),
                    routing_key=SOME_ROUTING_KEY,
                    headers={'name': ANOTHER_TRIGGER_EVENT_NAME})

        def callback_received():
            try:
                third_party.verify(
                    request={
                        'method': 'GET',
                        'path': '/test',
                        'body': '',
                    },
                    count=1,
                    exact=True
                )
            except Exception:
                raise AssertionError()

        until.assert_(callback_received, tries=10, interval=0.5)

    @subscription(TEST_SUBSCRIPTION)
    @subscription(TEST_SUBSCRIPTION)
    def test_given_two_http_subscriptions_when_update_config_then_callback_triggered_with_new_config(self, subscription, _):
        bus = self.make_bus()
        third_party = self.make_third_party()
        webhookd = self.make_webhookd(VALID_TOKEN)

        subscription['config']['url'] = 'http://third-party-http:1080/new-url'
        webhookd.subscriptions.update(subscription['uuid'], subscription)
        time.sleep(1)  # wait for the subscription to be updated

        bus.publish(trigger_event(),
                    routing_key=SOME_ROUTING_KEY,
                    headers={'name': TRIGGER_EVENT_NAME})

        def new_callback_received():
            try:
                third_party.verify(
                    request={
                        'method': 'GET',
                        'path': '/new-url',
                        'body': '',
                    },
                )
            except Exception:
                raise AssertionError()

        def old_callback_received_once():
            try:
                third_party.verify(
                    request={
                        'method': 'GET',
                        'path': '/test',
                        'body': '',
                    },
                    count=1,
                    exact=True,
                )
            except Exception:
                raise AssertionError()

        until.assert_(new_callback_received, tries=10, interval=0.5)
        until.assert_(old_callback_received_once, tries=10, interval=0.5)

    @subscription(TEST_SUBSCRIPTION)
    @subscription(TEST_SUBSCRIPTION)
    def test_given_two_http_subscription_when_one_deleted_then_one_http_callback(self, subscription, subscription_to_remove):
        bus = self.make_bus()
        third_party = self.make_third_party()
        webhookd = self.make_webhookd(VALID_TOKEN)

        webhookd.subscriptions.delete(subscription_to_remove['uuid'])
        time.sleep(1)  # wait for the subscription to be removed
        bus.publish(trigger_event(),
                    routing_key=SOME_ROUTING_KEY,
                    headers={'name': TRIGGER_EVENT_NAME})

        def callback_received_once():
            try:
                third_party.verify(
                    request={
                        'method': 'GET',
                        'path': '/test',
                        'body': '',
                    },
                    count=1,
                    exact=True,
                )
            except Exception:
                raise AssertionError()

        until.assert_(callback_received_once, tries=10, interval=0.5)

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_http_subscription_when_restart_webhookd_then_callback_still_triggered(self, subscription):
        third_party = self.make_third_party()
        bus = self.make_bus()

        self.restart_service('webhookd')
        ConnectedWaitStrategy().wait(self.make_webhookd(VALID_TOKEN))

        bus.publish(trigger_event(),
                    routing_key=SOME_ROUTING_KEY,
                    headers={'name': TRIGGER_EVENT_NAME})

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

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_http_subscription_when_restart_rabbitmq_then_callback_still_triggered(self, subscription):
        third_party = self.make_third_party()

        self.restart_service('rabbitmq')
        ConnectedWaitStrategy().wait(self.make_webhookd(VALID_TOKEN))

        bus = self.make_bus()
        bus.publish(trigger_event(),
                    routing_key=SOME_ROUTING_KEY,
                    headers={'name': TRIGGER_EVENT_NAME})

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

    @subscription(TEST_SUBSCRIPTION_URL_TEMPLATE)
    def test_given_http_subscription_with_url_template_when_bus_event_then_callback_with_url_templated(self, subscription):
        third_party = self.make_third_party()
        bus = self.make_bus()

        bus.publish(trigger_event(data={'variable': 'value', 'another_variable': 'another_value'}),
                    routing_key=SOME_ROUTING_KEY,
                    headers={'name': TRIGGER_EVENT_NAME})

        def callback_received():
            try:
                third_party.verify(
                    request={
                        'method': 'GET',
                        'path': '/test/value',
                        'queryStringParameters': [
                            {'name': 'variable', 'value': 'value'},
                            {'name': 'another_variable', 'value': 'another_value'}
                        ]
                    }
                )
            except Exception:
                raise AssertionError()

        until.assert_(callback_received, tries=10, interval=0.5)

    @subscription(TEST_SUBSCRIPTION_BODY)
    def test_given_one_http_subscription_with_body_when_bus_event_then_http_callback_with_body(self, subscription):
        third_party = self.make_third_party()
        bus = self.make_bus()

        bus.publish(trigger_event(),
                    routing_key=SOME_ROUTING_KEY,
                    headers={'name': TRIGGER_EVENT_NAME})

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

    @subscription(TEST_SUBSCRIPTION_BODY_TEMPLATE)
    def test_given_http_subscription_with_body_template_when_bus_event_then_callback_with_body_templated(self, subscription):
        third_party = self.make_third_party()
        bus = self.make_bus()

        bus.publish(trigger_event(data={'variable': 'value'}),
                    routing_key=SOME_ROUTING_KEY,
                    headers={'name': TRIGGER_EVENT_NAME})

        def callback_received():
            try:
                third_party.verify(
                    request={
                        'method': 'GET',
                        'path': '/test',
                        'body': 'trigger value',
                    }
                )
            except Exception:
                raise AssertionError()

        until.assert_(callback_received, tries=10, interval=0.5)

    @subscription(TEST_SUBSCRIPTION_VERIFY)
    def test_given_subscription_with_verify_cert_when_bus_event_then_http_callback_with_verify(self, subscription):
        third_party = self.make_third_party()
        bus = self.make_bus()

        bus.publish(trigger_event(), routing_key=SOME_ROUTING_KEY, headers={'name': TRIGGER_EVENT_NAME})

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

    @subscription(TEST_SUBSCRIPTION_CONTENT_TYPE)
    def test_given_http_subscription_with_content_type_when_bus_event_then_http_callback_with_content_type(self, subscription):
        third_party = self.make_third_party()
        bus = self.make_bus()

        bus.publish(trigger_event(), routing_key=SOME_ROUTING_KEY, headers={'name': TRIGGER_EVENT_NAME})

        def callback_received():
            try:
                third_party.verify(
                    request={
                        'method': 'POST',
                        'path': '/test',
                        'body': 'keỳ: vàlue',
                        'headers': [{'name': 'Content-Type',
                                     'values': ['text/yaml']}],
                    }
                )
            except Exception:
                raise AssertionError()

        until.assert_(callback_received, tries=10, interval=0.5)

    @subscription(TEST_SUBSCRIPTION_FILTER_USER_ALICE)
    def test_given_http_subscription_with_user_uuid_when_bus_events_then_only_callback_when_user_uuid_match(self, subscription):
        third_party = self.make_third_party()
        bus = self.make_bus()

        # Non-matching events
        bus.publish(trigger_event(), routing_key=SOME_ROUTING_KEY)
        bus.publish(trigger_event(),
                    routing_key=SOME_ROUTING_KEY,
                    headers={'name': TRIGGER_EVENT_NAME,
                             'user_uuid': BOB_USER_UUID})
        bus.publish(trigger_event(),
                    routing_key=SOME_ROUTING_KEY,
                    headers={'name': TRIGGER_EVENT_NAME,
                             'user_uuid': ALICE_USER_UUID_EXTENDED})
        # Matching event
        bus.publish(trigger_event(),
                    routing_key=SOME_ROUTING_KEY,
                    headers={'name': TRIGGER_EVENT_NAME,
                             'user_uuid': ALICE_USER_UUID})

        def callback_received_once():
            try:
                third_party.verify(
                    request={
                        'method': 'GET',
                        'path': '/test',
                    },
                    count=1,
                    exact=True,
                )
            except Exception:
                raise AssertionError()

        until.assert_(callback_received_once, tries=10, interval=0.5)
