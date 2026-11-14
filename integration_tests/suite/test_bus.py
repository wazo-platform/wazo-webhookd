# Copyright 2020-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import time

from hamcrest import (
    assert_that,
    contains_inanyorder,
    empty,
    equal_to,
    has_entries,
    has_item,
    is_not,
)
from mockserver import MockServerClient
from wazo_test_helpers import until
from wazo_test_helpers.bus import BusClient

from .helpers.base import (
    MASTER_TOKEN,
    OTHER_TENANT,
    USER_1_UUID,
    USER_2_UUID,
    USERS_TENANT,
    BaseIntegrationTest,
)
from .helpers.wait_strategy import ConnectedWaitStrategy

EVENT = 'bindings-test-event'
OTHER_EVENT = 'bindings-test-other-event'
MARKER_EVENT = 'bindings-test-marker'


class TestBusConsumer(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = ConnectedWaitStrategy()

    def setUp(self):
        super().setUp()
        bus_port = self.service_port(5672, 'rabbitmq')
        self.bus = BusClient.from_connection_fields(
            host='127.0.0.1',
            port=bus_port,
            exchange_name='wazo-headers',
            exchange_type='headers',
        )

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


class TestBusBindings(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = ConnectedWaitStrategy()

    def setUp(self):
        super().setUp()
        self.bus = self.make_bus()
        self.third_party = MockServerClient(
            f'http://127.0.0.1:{self.service_port(1080, "third-party-http")}'
        )
        self.third_party.reset()
        self.sentinel = self.make_sentinel()
        self.sentinel.reset()

    def subscribe(self, path, events, tenant=None, user_uuid=None):
        body = {
            'name': path,
            'service': 'http',
            'config': {'url': f'http://third-party-http:1080/{path}', 'method': 'get'},
            'events': events,
        }
        if user_uuid:
            body['events_user_uuid'] = user_uuid
        self.third_party.mock_simple_response(
            path=f'/{path}', responseBody='ok', statusCode=200
        )
        webhookd = self.make_webhookd(MASTER_TOKEN, tenant)
        subscription = webhookd.subscriptions.create(body)
        self.ensure_webhookd_consume_subscription(subscription)
        return subscription

    def publish(self, name, tenant_uuid, user_uuid=None):
        headers = {'name': name, 'tenant_uuid': tenant_uuid}
        if user_uuid:
            headers[f'user_uuid:{user_uuid}'] = True
        self.bus.publish(
            {'name': name, 'data': {}, 'origin_uuid': 'bindings-test'},
            headers=headers,
        )

    def calls(self, path):
        try:
            self.third_party.verify(
                request={'method': 'GET', 'path': f'/{path}'}, count=1, exact=True
            )
            return 1
        except Exception:
            pass
        try:
            self.third_party.verify(
                request={'method': 'GET', 'path': f'/{path}'}, count=0, exact=True
            )
            return 0
        except Exception:
            return 'more than one'

    def wait_for_marker(self):
        # the marker follows the events under test on the same queue, so once
        # it is received every message the broker routed before it has been too
        self.publish(MARKER_EVENT, USERS_TENANT)
        until.assert_(
            lambda: assert_that(
                self.sentinel.received(), has_item(has_entries(name=MARKER_EVENT))
            ),
            timeout=10,
            interval=0.5,
        )

    def received(self, name, tenant_uuid):
        return [
            headers
            for headers in self.sentinel.received()
            if headers.get('name') == name and headers.get('tenant_uuid') == tenant_uuid
        ]

    def test_a_user_event_reaches_its_user_and_the_admin_subscriptions_only(self):
        self.subscribe('marker', [MARKER_EVENT], tenant=USERS_TENANT)
        self.subscribe('user-1', [EVENT], tenant=USERS_TENANT, user_uuid=USER_1_UUID)
        self.subscribe('user-2', [EVENT], tenant=USERS_TENANT, user_uuid=USER_2_UUID)
        self.subscribe('admin', [EVENT], tenant=USERS_TENANT)

        self.publish(EVENT, USERS_TENANT, user_uuid=USER_1_UUID)
        self.wait_for_marker()

        until.assert_(
            lambda: assert_that(
                [self.calls('user-1'), self.calls('admin')], equal_to([1, 1])
            ),
            timeout=10,
            interval=0.5,
        )
        time.sleep(1)
        assert_that(
            [self.calls('user-1'), self.calls('user-2'), self.calls('admin')],
            equal_to([1, 0, 1]),
        )

    def test_another_tenants_event_reaches_the_queue_only_for_a_master_subscription(
        self,
    ):
        self.subscribe('marker', [MARKER_EVENT], tenant=USERS_TENANT)
        self.subscribe('admin', [EVENT], tenant=USERS_TENANT)

        self.publish(EVENT, OTHER_TENANT)
        self.wait_for_marker()

        assert_that(self.received(EVENT, OTHER_TENANT), empty())
        time.sleep(1)
        assert_that(self.calls('admin'), equal_to(0))

        self.subscribe('master', [EVENT])
        self.sentinel.reset()
        self.publish(EVENT, OTHER_TENANT)
        self.wait_for_marker()

        assert_that(self.received(EVENT, OTHER_TENANT), is_not(empty()))
        until.assert_(
            lambda: assert_that(self.calls('master'), equal_to(1)),
            timeout=10,
            interval=0.5,
        )
        time.sleep(1)
        assert_that([self.calls('admin'), self.calls('master')], equal_to([0, 1]))

    def test_the_broker_holds_one_queue_binding_per_event_name_and_tenant(self):
        for number in range(3):
            self.subscribe(
                f'users-{number}',
                [EVENT, OTHER_EVENT],
                tenant=USERS_TENANT,
                user_uuid=(USER_1_UUID, USER_2_UUID, None)[number],
            )
        for number in range(2):
            self.subscribe(f'other-{number}', [EVENT], tenant=OTHER_TENANT)
        subscription = self.subscribe('master', [EVENT])

        self.restart_service('webhookd')
        ConnectedWaitStrategy().wait(self.make_webhookd(MASTER_TOKEN))
        self.ensure_webhookd_consume_subscription(subscription)

        queue_bindings = [
            binding
            for binding in self.list_bindings()
            if binding['destination_kind'] == 'queue'
            and binding['destination_name'].startswith('wazo_webhookd.')
        ]
        [queue_name] = {binding['destination_name'] for binding in queue_bindings}
        tested = [
            binding['arguments']
            for binding in queue_bindings
            if EVENT in binding['arguments'] or OTHER_EVENT in binding['arguments']
        ]

        assert_that(
            [binding['source_name'] for binding in queue_bindings],
            has_item(''),
        )
        default = [b for b in queue_bindings if b['source_name'] == '']
        assert_that(
            [(b['routing_key'], b['arguments']) for b in default],
            equal_to([(queue_name, '[]')]),
        )
        assert_that(
            [
                binding['source_name']
                for binding in queue_bindings
                if binding not in default
            ],
            is_not(has_item(is_not('wazo_webhookd'))),
        )
        assert_that(
            [self.binding_key(arguments) for arguments in tested],
            contains_inanyorder(
                (EVENT, USERS_TENANT),
                (OTHER_EVENT, USERS_TENANT),
                (EVENT, OTHER_TENANT),
                (EVENT, None),
            ),
        )
        assert_that(
            [
                binding['arguments']
                for binding in queue_bindings
                if 'x-subscription' in binding['arguments']
                or 'user_uuid' in binding['arguments']
            ],
            empty(),
        )

    @staticmethod
    def binding_key(arguments):
        name = EVENT if f'"{EVENT}"' in arguments else OTHER_EVENT
        for tenant in (USERS_TENANT, OTHER_TENANT):
            if tenant in arguments:
                return name, tenant
        return name, None
