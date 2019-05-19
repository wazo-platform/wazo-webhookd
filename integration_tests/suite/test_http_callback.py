# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import requests

from hamcrest import assert_that
from hamcrest import is_
from mockserver import MockServerClient
from xivo_test_helpers import until

from .helpers.base import BaseIntegrationTest
from .helpers.base import VALID_TOKEN
from .helpers.fixtures import subscription
from .helpers.wait_strategy import ConnectedWaitStrategy

ALICE_USER_UUID = '19f216be-916c-415c-83b5-6a13af92dd86'
ALICE_USER_UUID_EXTENDED = '19f216be-916c-415c-83b5-6a13af92dd86-suffix'
BOB_USER_UUID = '19f216be-916c-415c-83b5-6a13af92dd87'
WAZO_UUID = 'cd030e68-ace9-4ad4-bc4e-13c8dec67898'
WAZO_UUID_EXTENDED = 'cd030e68-ace9-4ad4-bc4e-13c8dec67898-suffix'
OTHER_WAZO_UUID = 'cae3a160-6b01-4746-acd2-8588a768e54c'
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
TEST_SUBSCRIPTION_ANOTHER_TRIGGER = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://third-party-http:1080/test',
               'method': 'get'},
    'events': ['another-trigger']
}
TEST_SUBSCRIPTION_FILTER_USER_ALICE = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://third-party-http:1080/test',
               'method': 'get'},
    'events': ['trigger'],
    'events_user_uuid': ALICE_USER_UUID,
}
TEST_SUBSCRIPTION_LOCALHOST_SENTINEL = {
    'name': 'localhost',
    'service': 'http',
    'config': {'url': 'https://localhost:9300/1.0/sentinel',
               'method': 'post',
               'verify_certificate': 'false'},
    'events': ['trigger'],
    'events_user_uuid': ALICE_USER_UUID,
}
TEST_USER_SUBSCRIPTION_LOCALHOST_SENTINEL = {
    'name': 'localhost',
    'service': 'http',
    'config': {'url': 'https://localhost:9300/1.0/sentinel',
               'method': 'post',
               'verify_certificate': 'false'},
    'events': ['trigger'],
    'owner_user_uuid': ALICE_USER_UUID,
    'events_user_uuid': ALICE_USER_UUID,
}
TEST_SUBSCRIPTION_FILTER_WAZO_UUID = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://third-party-http:1080/test',
               'method': 'get'},
    'events': ['trigger'],
    'events_wazo_uuid': WAZO_UUID,
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

    def setUp(self):
        self.third_party = MockServerClient(
            'http://localhost:{port}'.format(port=self.service_port(1080, 'third-party-http'))
        )
        self.third_party.reset()
        self.sentinel = self.make_sentinel()
        self.sentinel.reset()
        self.bus = self.make_bus()

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_http_subscription_when_bus_event_then_one_http_callback(self, subscription):

        self.bus.publish(trigger_event(),
                         routing_key=SOME_ROUTING_KEY,
                         headers={'name': TRIGGER_EVENT_NAME})

        def callback_received():
            try:
                self.third_party.verify(
                    request={
                        'method': 'GET',
                        'path': '/test',
                    }
                )
            except Exception:
                raise AssertionError()

        until.assert_(callback_received, tries=10, interval=0.5)

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_http_subscription_when_update_events_then_callback_triggered_on_the_right_event(self, subscription):
        webhookd = self.make_webhookd(VALID_TOKEN)
        old_trigger_name = TRIGGER_EVENT_NAME

        subscription['events'] = [ANOTHER_TRIGGER_EVENT_NAME]
        webhookd.subscriptions.update(subscription['uuid'], subscription)
        self.ensure_webhookd_consume_uuid(subscription['uuid'])

        self.bus.publish(event(name=old_trigger_name),
                         routing_key=SOME_ROUTING_KEY,
                         headers={'name': old_trigger_name})
        self.bus.publish(event(name=ANOTHER_TRIGGER_EVENT_NAME),
                         routing_key=SOME_ROUTING_KEY,
                         headers={'name': ANOTHER_TRIGGER_EVENT_NAME})

        def callback_received():
            try:
                self.third_party.verify(
                    request={
                        'method': 'GET',
                        'path': '/test',
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
        webhookd = self.make_webhookd(VALID_TOKEN)

        subscription['config']['url'] = 'http://third-party-http:1080/new-url'
        webhookd.subscriptions.update(subscription['uuid'], subscription)
        self.ensure_webhookd_consume_uuid(subscription['uuid'])

        self.bus.publish(trigger_event(),
                         routing_key=SOME_ROUTING_KEY,
                         headers={'name': TRIGGER_EVENT_NAME})

        def new_callback_received():
            try:
                self.third_party.verify(
                    request={
                        'method': 'GET',
                        'path': '/new-url',
                    },
                )
            except Exception:
                raise AssertionError()

        def old_callback_received_once():
            try:
                self.third_party.verify(
                    request={
                        'method': 'GET',
                        'path': '/test',
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
        webhookd = self.make_webhookd(VALID_TOKEN)

        webhookd.subscriptions.delete(subscription_to_remove['uuid'])
        self.ensure_webhookd_not_consume_uuid(subscription_to_remove['uuid'])
        self.bus.publish(trigger_event(),
                         routing_key=SOME_ROUTING_KEY,
                         headers={'name': TRIGGER_EVENT_NAME})

        def callback_received_once():
            try:
                self.third_party.verify(
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

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_http_subscription_when_restart_webhookd_then_callback_still_triggered(self, subscription):

        self.restart_service('webhookd')
        ConnectedWaitStrategy().wait(self.make_webhookd(VALID_TOKEN))
        self.ensure_webhookd_consume_uuid(subscription['uuid'])

        self.bus.publish(trigger_event(),
                         routing_key=SOME_ROUTING_KEY,
                         headers={'name': TRIGGER_EVENT_NAME})

        def callback_received():
            try:
                self.third_party.verify(
                    request={
                        'method': 'GET',
                        'path': '/test',
                    }
                )
            except Exception:
                raise AssertionError()

        until.assert_(callback_received, tries=10, interval=0.5)

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_http_subscription_when_restart_rabbitmq_then_callback_still_triggered(self, subscription):

        self.restart_service('rabbitmq')
        ConnectedWaitStrategy().wait(self.make_webhookd(VALID_TOKEN))

        # FIXME(sileht): BusClient should reconnect automatically
        self.bus = self.make_bus()
        until.true(self.bus.is_up, tries=5, message='rabbitmq did not come back up')

        self.bus.publish(trigger_event(),
                         routing_key=SOME_ROUTING_KEY,
                         headers={'name': TRIGGER_EVENT_NAME})

        def callback_received():
            try:
                self.third_party.verify(
                    request={
                        'method': 'GET',
                        'path': '/test',
                    }
                )
            except Exception:
                raise AssertionError()

        until.assert_(callback_received, tries=10, interval=0.5)

    @subscription(TEST_SUBSCRIPTION_URL_TEMPLATE)
    def test_given_http_subscription_with_url_template_when_bus_event_then_callback_with_url_templated(self, subscription):

        self.bus.publish(trigger_event(data={'variable': 'value', 'another_variable': 'another_value'}),
                         routing_key=SOME_ROUTING_KEY,
                         headers={'name': TRIGGER_EVENT_NAME})

        def callback_received():
            try:
                self.third_party.verify(
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

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_http_subscription_with_no_body_when_bus_event_then_http_callback_with_default_body(self, subscription):

        self.bus.publish(trigger_event(data={'keý': 'vàlue'}),
                         routing_key=SOME_ROUTING_KEY,
                         headers={'name': TRIGGER_EVENT_NAME})

        def callback_received():
            try:
                self.third_party.verify(
                    request={
                        'method': 'GET',
                        'path': '/test',
                        'body': '{"ke\\u00fd": "v\\u00e0lue"}',
                        'headers': [{'name': 'Content-Type',
                                     'values': ['application/json']}],
                    }
                )
            except Exception:
                raise AssertionError()

        until.assert_(callback_received, tries=10, interval=0.5)

    @subscription(TEST_SUBSCRIPTION_BODY)
    def test_given_one_http_subscription_with_body_when_bus_event_then_http_callback_with_body(self, subscription):

        self.bus.publish(trigger_event(),
                         routing_key=SOME_ROUTING_KEY,
                         headers={'name': TRIGGER_EVENT_NAME})

        def callback_received():
            try:
                self.third_party.verify(
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

        self.bus.publish(trigger_event(data={'variable': 'value'}),
                         routing_key=SOME_ROUTING_KEY,
                         headers={'name': TRIGGER_EVENT_NAME})

        def callback_received():
            try:
                self.third_party.verify(
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

        self.bus.publish(trigger_event(), routing_key=SOME_ROUTING_KEY, headers={'name': TRIGGER_EVENT_NAME})

        def callback_received():
            try:
                self.third_party.verify(
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

        self.bus.publish(trigger_event(), routing_key=SOME_ROUTING_KEY, headers={'name': TRIGGER_EVENT_NAME})

        def callback_received():
            try:
                self.third_party.verify(
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

        # Non-matching events
        self.bus.publish(trigger_event(), routing_key=SOME_ROUTING_KEY)
        self.bus.publish(trigger_event(),
                         routing_key=SOME_ROUTING_KEY,
                         headers={'name': TRIGGER_EVENT_NAME,
                                  'user_uuid:{uuid}'.format(uuid=BOB_USER_UUID): True})
        self.bus.publish(trigger_event(),
                         routing_key=SOME_ROUTING_KEY,
                         headers={'name': TRIGGER_EVENT_NAME,
                                  'user_uuid:{uuid}'.format(uuid=ALICE_USER_UUID_EXTENDED): True})
        # Matching event
        self.bus.publish(trigger_event(),
                         routing_key=SOME_ROUTING_KEY,
                         headers={'name': TRIGGER_EVENT_NAME,
                                  'user_uuid:{uuid}'.format(uuid=ALICE_USER_UUID): True})

        def callback_received_once():
            try:
                self.third_party.verify(
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

    @subscription(TEST_SUBSCRIPTION_ANOTHER_TRIGGER)
    @subscription(TEST_USER_SUBSCRIPTION_LOCALHOST_SENTINEL)
    def test_given_http_user_subscription_to_localhost_when_bus_event_then_callback_not_called(self, control_subscription, sentinel_subscription):
        # sentinel should not be triggered
        self.bus.publish(trigger_event(),
                         routing_key=SOME_ROUTING_KEY,
                         headers={'name': TRIGGER_EVENT_NAME,
                                  'user_uuid:{uuid}'.format(uuid=ALICE_USER_UUID): True})
        # trigger control webhook
        self.bus.publish(event(name=ANOTHER_TRIGGER_EVENT_NAME),
                         routing_key=SOME_ROUTING_KEY,
                         headers={'name': ANOTHER_TRIGGER_EVENT_NAME,
                                  'user_uuid:{uuid}'.format(uuid=ALICE_USER_UUID): True})

        def control_callback_received_once():
            try:
                self.third_party.verify(
                    request={
                        'method': 'GET',
                        'path': '/test',
                    },
                    count=1,
                    exact=True,
                )
            except Exception:
                raise AssertionError()

        until.assert_(control_callback_received_once, tries=10, interval=0.5)
        assert_that(self.sentinel.called(), is_(False))

    @subscription(TEST_SUBSCRIPTION_LOCALHOST_SENTINEL)
    def test_given_http_subscription_to_localhost_when_bus_event_then_callback_called(self, subscription):
        self.bus.publish(trigger_event(),
                         routing_key=SOME_ROUTING_KEY,
                         headers={'name': TRIGGER_EVENT_NAME,
                                  'user_uuid:{uuid}'.format(uuid=ALICE_USER_UUID): True})

        def sentinel_was_called():
            assert_that(self.sentinel.called(), is_(True))

        until.assert_(sentinel_was_called, tries=10, interval=0.5)

    @subscription(TEST_SUBSCRIPTION_FILTER_WAZO_UUID)
    def test_given_http_subscription_with_wazo_uuid_when_bus_events_then_only_callback_when_wazo_uuid_match(self, subscription):
        # Non-matching events
        self.bus.publish(trigger_event(), routing_key=SOME_ROUTING_KEY)
        self.bus.publish(trigger_event(),
                         routing_key=SOME_ROUTING_KEY,
                         headers={'name': TRIGGER_EVENT_NAME,
                                  'origin_uuid': OTHER_WAZO_UUID})
        self.bus.publish(trigger_event(),
                         routing_key=SOME_ROUTING_KEY,
                         headers={'name': TRIGGER_EVENT_NAME,
                                  'origin_uuid': WAZO_UUID_EXTENDED})
        # Matching event
        self.bus.publish(trigger_event(),
                         routing_key=SOME_ROUTING_KEY,
                         headers={'name': TRIGGER_EVENT_NAME,
                                  'origin_uuid': WAZO_UUID})

        def callback_received_once():
            try:
                self.third_party.verify(
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
