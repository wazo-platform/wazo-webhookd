# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
import operator

from hamcrest import assert_that, contains, contains_string, has_entries, is_
from mockserver import MockServerClient
from xivo_test_helpers import until

from .helpers.base import BaseIntegrationTest
from .helpers.base import MASTER_TOKEN
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
    'config': {'url': 'http://third-party-http:1080/test', 'method': 'get'},
    'events': ['trigger'],
}
TEST_SUBSCRIPTION_BODY = {
    'name': 'test',
    'service': 'http',
    'config': {
        'url': 'http://third-party-http:1080/test',
        'method': 'get',
        'body': '{"body_keỳ": "body_vàlue"}',
    },
    'events': ['trigger'],
}
TEST_SUBSCRIPTION_URL_TEMPLATE = {
    'name': 'test',
    'service': 'http',
    'config': {
        'url': 'http://third-party-http:1080/test/{{ event["variable"] }}?{{ event|urlencode }}',
        'method': 'get',
    },
    'events': ['trigger'],
}
TEST_SUBSCRIPTION_BODY_TEMPLATE = {
    'name': 'test',
    'service': 'http',
    'config': {
        'url': 'http://third-party-http:1080/test',
        'method': 'get',
        'body': '{{ event_name }} {{ event["variable"] }}',
    },
    'events': ['trigger'],
}
TEST_SUBSCRIPTION_VERIFY = {
    'name': 'test',
    'service': 'http',
    'config': {
        'url': 'https://third-party-http:1080/test',
        'method': 'get',
        'verify_certificate': 'false',
    },
    'events': ['trigger'],
}
TEST_SUBSCRIPTION_CONTENT_TYPE = {
    'name': 'test',
    'service': 'http',
    'config': {
        'url': 'http://third-party-http:1080/test',
        'method': 'post',
        'body': 'keỳ: vàlue',
        'content_type': 'text/yaml',
    },
    'events': ['trigger'],
}
TEST_SUBSCRIPTION_NO_TRIGGER = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://third-party-http:1080/test', 'method': 'get'},
    'events': ['dont-trigger'],
}
TEST_SUBSCRIPTION_ANOTHER_TRIGGER = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://third-party-http:1080/test', 'method': 'get'},
    'events': ['another-trigger'],
}
TEST_SUBSCRIPTION_FILTER_USER_ALICE = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://third-party-http:1080/test', 'method': 'get'},
    'events': ['trigger'],
    'events_user_uuid': ALICE_USER_UUID,
}
TEST_SUBSCRIPTION_LOCALHOST_SENTINEL = {
    'name': 'localhost',
    'service': 'http',
    'config': {
        'url': 'https://localhost:9300/1.0/sentinel',
        'method': 'post',
        'verify_certificate': 'false',
    },
    'events': ['trigger'],
    'events_user_uuid': ALICE_USER_UUID,
}
TEST_USER_SUBSCRIPTION_LOCALHOST_SENTINEL = {
    'name': 'localhost',
    'service': 'http',
    'config': {
        'url': 'https://localhost:9300/1.0/sentinel',
        'method': 'post',
        'verify_certificate': 'false',
    },
    'events': ['trigger'],
    'owner_user_uuid': ALICE_USER_UUID,
    'events_user_uuid': ALICE_USER_UUID,
}
TEST_SUBSCRIPTION_FILTER_WAZO_UUID = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://third-party-http:1080/test', 'method': 'get'},
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

    def make_third_party_verify_callback(self, *args, **kwargs):
        def callback():
            try:
                self.third_party.verify(*args, **kwargs)
            except Exception as e:
                if str(e) == "Failed to verify":
                    raise AssertionError()
                else:
                    raise

        return callback

    def setUp(self):
        super(TestHTTPCallback, self).__init__()
        self.third_party = MockServerClient(
            'http://localhost:{port}'.format(
                port=self.service_port(1080, 'third-party-http')
            )
        )
        self.third_party.reset()
        self.third_party.mock_simple_response(
            path='/test', responseBody="working service", statusCode=200
        )

        self.sentinel = self.make_sentinel()
        self.sentinel.reset()
        self.bus = self.make_bus()

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_http_subscription_when_bus_event_then_one_http_callback(
        self, subscription
    ):

        self.bus.publish(
            trigger_event(),
            routing_key=SOME_ROUTING_KEY,
            headers={'name': TRIGGER_EVENT_NAME},
        )

        until.assert_(
            self.make_third_party_verify_callback(
                request={'method': 'GET', 'path': '/test'}, count=1, exact=True
            ),
            tries=10,
            interval=0.5,
        )

        webhookd = self.make_webhookd(MASTER_TOKEN)
        logs = webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], 1)
        assert_that(logs['items'][0], has_entries(status="success", attempts=1))

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_http_subscription_when_bus_event_then_one_http_callback_with_json(
        self, subscription
    ):
        body = {"some": "json", "as": "payload"}

        self.third_party.reset()
        self.third_party.mock_simple_response(
            path='/test', responseBody=body, statusCode=200
        )

        self.bus.publish(
            trigger_event(),
            routing_key=SOME_ROUTING_KEY,
            headers={'name': TRIGGER_EVENT_NAME},
        )

        until.assert_(
            self.make_third_party_verify_callback(
                request={'method': 'GET', 'path': '/test'}, count=1, exact=True
            ),
            tries=10,
            interval=0.5,
        )

        webhookd = self.make_webhookd(MASTER_TOKEN)
        logs = webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], 1)
        assert_that(
            logs['items'][0],
            has_entries(
                status="success", detail=has_entries(response_body=body), attempts=1
            ),
        )

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_http_subscription_when_bus_event_then_one_http_callback_that_return_410(
        self, subscription
    ):
        self.third_party.reset()
        self.third_party.mock_simple_response(
            path='/test', responseBody="Gone", statusCode=410
        )

        self.bus.publish(
            trigger_event(),
            routing_key=SOME_ROUTING_KEY,
            headers={'name': TRIGGER_EVENT_NAME},
        )

        until.assert_(
            self.make_third_party_verify_callback(
                request={'method': 'GET', 'path': '/test'}, count=1, exact=True
            ),
            tries=10,
            interval=0.5,
        )

        webhookd = self.make_webhookd(MASTER_TOKEN)
        logs = webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], 1)
        assert_that(
            logs['items'][0],
            has_entries(
                status="error",
                detail=has_entries(error=contains_string("Gone")),
                attempts=1,
            ),
        )

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_http_subscription_when_bus_event_then_one_http_callback_that_return_500(
        self, subscription
    ):
        self.third_party.reset()
        self.third_party.mock_simple_response(
            path='/test', responseBody="temporary bugged service", statusCode=503
        )
        self.third_party.mock_simple_response(
            path='/test', responseBody="working service", statusCode=200
        )

        self.bus.publish(
            trigger_event(),
            routing_key=SOME_ROUTING_KEY,
            headers={'name': TRIGGER_EVENT_NAME},
        )

        until.assert_(
            self.make_third_party_verify_callback(
                request={'method': 'GET', 'path': '/test'}, count=2, exact=True
            ),
            tries=10,
            interval=0.5,
        )

        webhookd = self.make_webhookd(MASTER_TOKEN)
        logs = webhookd.subscriptions.get_logs(subscription["uuid"], direction="asc")
        self.assertEqual(2, logs['total'])

        assert_that(logs['total'], 2)
        assert_that(
            logs['items'],
            contains(
                has_entries(
                    status="failure",
                    detail=has_entries(error=contains_string("Service Unavailable")),
                    attempts=1,
                ),
                has_entries(
                    status="success",
                    attempts=2,
                    detail=has_entries(
                        request_method="GET",
                        request_url=(
                            'http://third-party-http:1080/test?'
                            'test_case=test_given_one_http_subscription_when_bus_event_then_one_http_callback_that_return_500'
                        ),
                    ),
                ),
            ),
        )

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_http_subscription_when_update_events_then_callback_triggered_on_the_right_event(
        self, subscription
    ):
        webhookd = self.make_webhookd(MASTER_TOKEN)
        old_trigger_name = TRIGGER_EVENT_NAME

        subscription['events'] = [ANOTHER_TRIGGER_EVENT_NAME]
        webhookd.subscriptions.update(subscription['uuid'], subscription)
        self.ensure_webhookd_consume_uuid(subscription['uuid'])

        self.bus.publish(
            event(name=old_trigger_name),
            routing_key=SOME_ROUTING_KEY,
            headers={'name': old_trigger_name},
        )
        self.bus.publish(
            event(name=ANOTHER_TRIGGER_EVENT_NAME),
            routing_key=SOME_ROUTING_KEY,
            headers={'name': ANOTHER_TRIGGER_EVENT_NAME},
        )

        until.assert_(
            self.make_third_party_verify_callback(
                request={'method': 'GET', 'path': '/test'}, count=1, exact=True
            ),
            tries=10,
            interval=0.5,
        )

    @subscription(TEST_SUBSCRIPTION)
    @subscription(TEST_SUBSCRIPTION)
    def test_given_two_http_subscriptions_when_update_config_then_callback_triggered_with_new_config(
        self, subscription, _
    ):
        webhookd = self.make_webhookd(MASTER_TOKEN)

        subscription['config']['url'] = 'http://third-party-http:1080/new-url'
        webhookd.subscriptions.update(subscription['uuid'], subscription)
        self.ensure_webhookd_consume_uuid(subscription['uuid'])

        self.bus.publish(
            trigger_event(),
            routing_key=SOME_ROUTING_KEY,
            headers={'name': TRIGGER_EVENT_NAME},
        )

        until.assert_(
            self.make_third_party_verify_callback(
                request={'method': 'GET', 'path': '/new-url'}
            ),
            tries=10,
            interval=0.5,
        )
        until.assert_(
            self.make_third_party_verify_callback(
                request={'method': 'GET', 'path': '/test'}, count=1, exact=True
            ),
            tries=10,
            interval=0.5,
        )

    @subscription(TEST_SUBSCRIPTION)
    @subscription(TEST_SUBSCRIPTION)
    def test_given_two_http_subscription_when_one_deleted_then_one_http_callback(
        self, subscription, subscription_to_remove
    ):
        webhookd = self.make_webhookd(MASTER_TOKEN)

        webhookd.subscriptions.delete(subscription_to_remove['uuid'])
        self.ensure_webhookd_not_consume_uuid(subscription_to_remove['uuid'])
        self.bus.publish(
            trigger_event(),
            routing_key=SOME_ROUTING_KEY,
            headers={'name': TRIGGER_EVENT_NAME},
        )

        until.assert_(
            self.make_third_party_verify_callback(
                request={'method': 'GET', 'path': '/test'}, count=1, exact=True
            ),
            tries=10,
            interval=0.5,
        )

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_http_subscription_when_restart_webhookd_then_callback_still_triggered(
        self, subscription
    ):

        self.restart_service('webhookd')
        ConnectedWaitStrategy().wait(self.make_webhookd(MASTER_TOKEN))
        self.ensure_webhookd_consume_uuid(subscription['uuid'])

        self.bus.publish(
            trigger_event(),
            routing_key=SOME_ROUTING_KEY,
            headers={'name': TRIGGER_EVENT_NAME},
        )

        until.assert_(
            self.make_third_party_verify_callback(
                request={'method': 'GET', 'path': '/test'}
            ),
            tries=10,
            interval=0.5,
        )

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_http_subscription_when_restart_rabbitmq_then_callback_still_triggered(
        self, subscription
    ):

        self.restart_service('rabbitmq')
        ConnectedWaitStrategy().wait(self.make_webhookd(MASTER_TOKEN))

        # FIXME(sileht): BusClient should reconnect automatically
        self.bus = self.make_bus()
        until.true(self.bus.is_up, tries=5, message='rabbitmq did not come back up')

        self.bus.publish(
            trigger_event(),
            routing_key=SOME_ROUTING_KEY,
            headers={'name': TRIGGER_EVENT_NAME},
        )

        until.assert_(
            self.make_third_party_verify_callback(
                request={'method': 'GET', 'path': '/test'}
            ),
            tries=10,
            interval=0.5,
        )

    @subscription(TEST_SUBSCRIPTION_URL_TEMPLATE)
    def test_given_http_subscription_with_url_template_when_bus_event_then_callback_with_url_templated(
        self, subscription
    ):
        self.third_party.reset()
        self.third_party.mock_simple_response(
            path='/test/value', responseBody="working service", statusCode=200
        )

        self.bus.publish(
            trigger_event(
                data={'variable': 'value', 'another_variable': 'another_value'}
            ),
            routing_key=SOME_ROUTING_KEY,
            headers={'name': TRIGGER_EVENT_NAME},
        )
        until.assert_(
            self.make_third_party_verify_callback(
                request={
                    'method': 'GET',
                    'path': '/test/value',
                    'queryStringParameters': [
                        {'name': 'variable', 'value': 'value'},
                        {'name': 'another_variable', 'value': 'another_value'},
                    ],
                }
            ),
            tries=10,
            interval=0.5,
        )

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_http_subscription_with_no_body_when_bus_event_then_http_callback_with_default_body(
        self, subscription
    ):

        self.bus.publish(
            trigger_event(data={'keý': 'vàlue'}),
            routing_key=SOME_ROUTING_KEY,
            headers={'name': TRIGGER_EVENT_NAME},
        )

        until.assert_(
            self.make_third_party_verify_callback(
                request={
                    'method': 'GET',
                    'path': '/test',
                    'body': '{"ke\\u00fd": "v\\u00e0lue"}',
                    'headers': [
                        {'name': 'Content-Type', 'values': ['application/json']}
                    ],
                }
            ),
            tries=10,
            interval=0.5,
        )

    @subscription(TEST_SUBSCRIPTION_BODY)
    def test_given_one_http_subscription_with_body_when_bus_event_then_http_callback_with_body(
        self, subscription
    ):

        self.bus.publish(
            trigger_event(),
            routing_key=SOME_ROUTING_KEY,
            headers={'name': TRIGGER_EVENT_NAME},
        )

        until.assert_(
            self.make_third_party_verify_callback(
                request={
                    'method': 'GET',
                    'path': '/test',
                    'body': '{"body_keỳ": "body_vàlue"}',
                }
            ),
            tries=10,
            interval=0.5,
        )

    @subscription(TEST_SUBSCRIPTION_BODY_TEMPLATE)
    def test_given_http_subscription_with_body_template_when_bus_event_then_callback_with_body_templated(
        self, subscription
    ):

        self.bus.publish(
            trigger_event(data={'variable': 'value'}),
            routing_key=SOME_ROUTING_KEY,
            headers={'name': TRIGGER_EVENT_NAME},
        )

        until.assert_(
            self.make_third_party_verify_callback(
                request={'method': 'GET', 'path': '/test', 'body': 'trigger value'}
            ),
            tries=10,
            interval=0.5,
        )

        webhookd = self.make_webhookd(MASTER_TOKEN)
        logs = webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], 1)
        assert_that(
            logs['items'],
            contains(
                has_entries(
                    status="success",
                    detail=has_entries(request_body='trigger value'),
                    attempts=1,
                )
            ),
        )

    @subscription(TEST_SUBSCRIPTION_VERIFY)
    def test_given_subscription_with_verify_cert_when_bus_event_then_http_callback_with_verify(
        self, subscription
    ):

        self.bus.publish(
            trigger_event(),
            routing_key=SOME_ROUTING_KEY,
            headers={'name': TRIGGER_EVENT_NAME},
        )

        until.assert_(
            self.make_third_party_verify_callback(
                request={'method': 'GET', 'path': '/test'}
            ),
            tries=10,
            interval=0.5,
        )

    @subscription(TEST_SUBSCRIPTION_CONTENT_TYPE)
    def test_given_http_subscription_with_content_type_when_bus_event_then_http_callback_with_content_type(
        self, subscription
    ):

        self.bus.publish(
            trigger_event(),
            routing_key=SOME_ROUTING_KEY,
            headers={'name': TRIGGER_EVENT_NAME},
        )

        until.assert_(
            self.make_third_party_verify_callback(
                request={
                    'method': 'POST',
                    'path': '/test',
                    'body': 'keỳ: vàlue',
                    'headers': [{'name': 'Content-Type', 'values': ['text/yaml']}],
                }
            ),
            tries=10,
            interval=0.5,
        )

    @subscription(TEST_SUBSCRIPTION_FILTER_USER_ALICE)
    def test_given_http_subscription_with_user_uuid_when_bus_events_then_only_callback_when_user_uuid_match(
        self, subscription
    ):

        # Non-matching events
        self.bus.publish(trigger_event(), routing_key=SOME_ROUTING_KEY)
        self.bus.publish(
            trigger_event(),
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': TRIGGER_EVENT_NAME,
                'user_uuid:{uuid}'.format(uuid=BOB_USER_UUID): True,
            },
        )
        self.bus.publish(
            trigger_event(),
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': TRIGGER_EVENT_NAME,
                'user_uuid:{uuid}'.format(uuid=ALICE_USER_UUID_EXTENDED): True,
            },
        )
        # Matching event
        self.bus.publish(
            trigger_event(),
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': TRIGGER_EVENT_NAME,
                'user_uuid:{uuid}'.format(uuid=ALICE_USER_UUID): True,
            },
        )

        until.assert_(
            self.make_third_party_verify_callback(
                request={'method': 'GET', 'path': '/test'}, count=1, exact=True
            ),
            tries=10,
            interval=0.5,
        )

    @subscription(TEST_SUBSCRIPTION_ANOTHER_TRIGGER)
    @subscription(TEST_USER_SUBSCRIPTION_LOCALHOST_SENTINEL)
    def test_given_http_user_subscription_to_localhost_when_bus_event_then_callback_not_called(
        self, control_subscription, sentinel_subscription
    ):
        # sentinel should not be triggered
        self.bus.publish(
            trigger_event(),
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': TRIGGER_EVENT_NAME,
                'user_uuid:{uuid}'.format(uuid=ALICE_USER_UUID): True,
            },
        )
        # trigger control webhook
        self.bus.publish(
            event(name=ANOTHER_TRIGGER_EVENT_NAME),
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': ANOTHER_TRIGGER_EVENT_NAME,
                'user_uuid:{uuid}'.format(uuid=ALICE_USER_UUID): True,
            },
        )

        until.assert_(
            self.make_third_party_verify_callback(
                request={'method': 'GET', 'path': '/test'}, count=1, exact=True
            ),
            tries=10,
            interval=0.5,
        )
        assert_that(self.sentinel.called(), is_(False))

    @subscription(TEST_SUBSCRIPTION_LOCALHOST_SENTINEL)
    def test_given_http_subscription_to_localhost_when_bus_event_then_callback_called(
        self, subscription
    ):
        self.bus.publish(
            trigger_event(),
            routing_key=SOME_ROUTING_KEY,
            headers={
                'name': TRIGGER_EVENT_NAME,
                'user_uuid:{uuid}'.format(uuid=ALICE_USER_UUID): True,
            },
        )

        def sentinel_was_called():
            assert_that(self.sentinel.called(), is_(True))

        until.assert_(sentinel_was_called, tries=10, interval=0.5)

    @subscription(TEST_SUBSCRIPTION_FILTER_WAZO_UUID)
    def test_given_http_subscription_with_wazo_uuid_when_bus_events_then_only_callback_when_wazo_uuid_match(
        self, subscription
    ):
        # Non-matching events
        self.bus.publish(trigger_event(), routing_key=SOME_ROUTING_KEY)
        self.bus.publish(
            trigger_event(),
            routing_key=SOME_ROUTING_KEY,
            headers={'name': TRIGGER_EVENT_NAME, 'origin_uuid': OTHER_WAZO_UUID},
        )
        self.bus.publish(
            trigger_event(),
            routing_key=SOME_ROUTING_KEY,
            headers={'name': TRIGGER_EVENT_NAME, 'origin_uuid': WAZO_UUID_EXTENDED},
        )
        # Matching event
        self.bus.publish(
            trigger_event(),
            routing_key=SOME_ROUTING_KEY,
            headers={'name': TRIGGER_EVENT_NAME, 'origin_uuid': WAZO_UUID},
        )
        until.assert_(
            self.make_third_party_verify_callback(
                request={'method': 'GET', 'path': '/test'}, count=1, exact=True
            ),
            tries=10,
            interval=0.5,
        )

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_http_subscription_check_pagination(self, subscription):
        self.third_party.reset()
        self.third_party.mock_simple_response(
            path='/test', responseBody="temporary bugged service", statusCode=503
        )
        self.third_party.mock_simple_response(
            path='/test', responseBody="temporary bugged service", statusCode=503
        )
        self.third_party.mock_simple_response(
            path='/test', responseBody="working service", statusCode=200
        )
        self.bus.publish(
            trigger_event(),
            routing_key=SOME_ROUTING_KEY,
            headers={'name': TRIGGER_EVENT_NAME},
        )

        until.assert_(
            self.make_third_party_verify_callback(
                request={'method': 'GET', 'path': '/test'}, count=3, exact=True
            ),
            tries=20,
            interval=0.5,
        )

        self.third_party.reset()
        self.third_party.mock_simple_response(
            path='/test', responseBody="temporary bugged service", statusCode=503
        )
        self.third_party.mock_simple_response(
            path='/test', responseBody="working service", statusCode=200
        )

        self.bus.publish(
            trigger_event(),
            routing_key=SOME_ROUTING_KEY,
            headers={'name': TRIGGER_EVENT_NAME},
        )

        until.assert_(
            self.make_third_party_verify_callback(
                request={'method': 'GET', 'path': '/test'}, count=2, exact=True
            ),
            tries=20,
            interval=0.5,
        )

        webhookd = self.make_webhookd(MASTER_TOKEN)

        # Default order
        logs = webhookd.subscriptions.get_logs(subscription["uuid"])
        assert_that(logs['total'], 5)
        assert_that(
            logs['items'],
            contains(
                has_entries(status="success"),
                has_entries(status="failure"),
                has_entries(status="success"),
                has_entries(status="failure"),
                has_entries(status="failure"),
            ),
        )
        sorted_items = sorted(
            logs['items'], reverse=True, key=operator.itemgetter("started_at")
        )
        assert_that(logs['items'], sorted_items)

        # reverse order
        logs = webhookd.subscriptions.get_logs(subscription["uuid"], direction="asc")
        assert_that(logs['total'], 5)
        assert_that(
            logs['items'],
            contains(
                has_entries(status="failure"),
                has_entries(status="failure"),
                has_entries(status="success"),
                has_entries(status="failure"),
                has_entries(status="success"),
            ),
        )
        all_sorted_items = sorted(logs['items'], key=operator.itemgetter("started_at"))
        assert_that(logs['items'], all_sorted_items)

        # limit 2
        logs = webhookd.subscriptions.get_logs(
            subscription["uuid"], limit=2, direction="asc"
        )
        assert_that(logs['total'], 2)
        assert_that(
            logs['items'],
            contains(has_entries(status="failure"), has_entries(status="failure")),
        )
        sorted_items = sorted(logs['items'], key=operator.itemgetter("started_at"))
        assert_that(all_sorted_items[:2], sorted_items)

        # limit 2 and offset 2
        logs = webhookd.subscriptions.get_logs(
            subscription["uuid"], limit=2, offset=2, direction="asc"
        )
        assert_that(logs['total'], 2)
        assert_that(
            logs['items'],
            contains(has_entries(status="success"), has_entries(status="failure")),
        )
        sorted_items = sorted(logs['items'], key=operator.itemgetter("started_at"))
        assert_that(all_sorted_items[2:4], sorted_items)

        # limit 2, offset 2 and from_date
        logs = webhookd.subscriptions.get_logs(
            subscription["uuid"],
            limit=2,
            offset=2,
            from_date=all_sorted_items[1]['started_at'],
            direction="asc",
        )
        assert_that(logs['total'], 2)
        assert_that(
            logs['items'],
            contains(has_entries(status="failure"), has_entries(status="success")),
        )
        sorted_items = sorted(logs['items'], key=operator.itemgetter("started_at"))
        assert_that(all_sorted_items[3:5], sorted_items)

        # by status
        logs = webhookd.subscriptions.get_logs(subscription["uuid"], order="status")
        assert_that(logs['total'], 5)
        assert_that(
            logs['items'],
            contains(
                has_entries(status="failure"),
                has_entries(status="failure"),
                has_entries(status="failure"),
                has_entries(status="success"),
                has_entries(status="success"),
            ),
        )
