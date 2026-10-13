# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import json
import logging
import re
import threading
import uuid
from collections import Counter
from pathlib import Path
from threading import Event, Thread
from typing import Any
from unittest.mock import PropertyMock, patch

import pytest
from xivo.pubsub import Pubsub
from xivo.status import StatusAggregator

from wazo_webhookd.bus import (
    LOG_PREFIX,
    BusConsumer,
    SubscriptionRegistrar,
    WebhookdExchange,
    retry_delay,
)
from wazo_webhookd.database.models import Subscription
from wazo_webhookd.plugins.subscription.bus import SubscriptionBusEventHandler
from wazo_webhookd.services.mobile.plugin import Service as MobileService

MASTER_TENANT = '00000000-0000-4000-8000-000000000001'
SECRET = 'secret-broker-password'


class ConcurrentUse(AssertionError):
    pass


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class FakeBroker:
    """Records what reached the broker. A connection belongs to the first
    thread that uses it, as a py-amqp one must (BUG-646): a second thread
    raises, and the violation is kept even if the caller swallows it."""

    def __init__(self, clock: FakeClock | None = None) -> None:
        self.clock = clock or FakeClock()
        self.exchange_binds: Counter[str] = Counter()
        self.queue_bindings: set[str] = set()
        self.frames = 0
        self.violations: list[str] = []
        self.bind_failures: dict[str, int] = {}
        self.queue_bind_failures: dict[str, int] = {}
        self.refuse_until = 0.0
        self.connects = 0
        self.releases = 0


class FakeChannel:
    def __init__(self, connection: FakeConnection) -> None:
        self._connection = connection

    def _frame(self) -> FakeBroker:
        self._connection.use()
        broker = self._connection.broker
        broker.frames += 1
        return broker

    def exchange_declare(self, *args, **kwargs) -> None:
        self._frame()

    def exchange_bind(
        self, destination, source, routing_key='', nowait=False, arguments=None
    ):
        broker = self._frame()
        name = arguments['name']
        if broker.bind_failures.get(name):
            broker.bind_failures[name] -= 1
            raise ConnectionResetError(f'amqp://guest:{SECRET}@localhost:5672//')
        broker.exchange_binds[name] += 1

    def queue_bind(self, queue, exchange, routing_key='', arguments=None, nowait=False):
        broker = self._frame()
        key = json.dumps(arguments, sort_keys=True)
        if broker.queue_bind_failures.get(arguments['name']):
            broker.queue_bind_failures[arguments['name']] -= 1
            raise ConnectionError('queue bind refused')
        broker.queue_bindings.add(key)

    def close(self) -> None:
        pass


class FakeConnection:
    connection_errors = (ConnectionError,)
    channel_errors = ()

    def __init__(self, broker: FakeBroker) -> None:
        self.broker = broker
        self.connected = False
        self._owner: int | None = None

    def use(self) -> None:
        me = threading.get_ident()
        if self._owner is None:
            self._owner = me
        elif self._owner != me:
            message = 'one AMQP connection used by two threads'
            self.broker.violations.append(message)
            raise ConcurrentUse(message)

    def clone(self) -> FakeConnection:
        return FakeConnection(self.broker)

    def connect(self) -> None:
        self.use()
        if self.broker.clock() < self.broker.refuse_until:
            raise ConnectionRefusedError(111, 'Connection refused')
        self.broker.connects += 1
        self.connected = True

    @property
    def default_channel(self) -> FakeChannel:
        self.use()
        return FakeChannel(self)

    def channel(self) -> FakeChannel:
        return FakeChannel(self)

    def release(self) -> None:
        self.broker.releases += 1
        self.connected = False


class FakeSubscriptionService:
    pubsub: Pubsub

    def __init__(self, subscriptions: list[Subscription] | None = None) -> None:
        self.pubsub = Pubsub()
        self.subscriptions = list(subscriptions or [])

    def list(
        self, owner_user_uuid=None, owner_tenant_uuids=None, search_metadata=None, **_
    ):
        result = self.subscriptions
        if owner_user_uuid:
            result = [s for s in result if s.owner_user_uuid == owner_user_uuid]
        if owner_tenant_uuids:
            result = [s for s in result if s.owner_tenant_uuid in owner_tenant_uuids]
        if search_metadata:
            result = [
                s
                for s in result
                if all(s.metadata_.get(k) == v for k, v in search_metadata.items())
            ]
        return list(result)

    def create(self, new_subscription: dict) -> Subscription:
        subscription = make_subscription(**new_subscription)
        self.subscriptions.append(subscription)
        self.pubsub.publish('created', subscription)
        return subscription

    def delete(self, subscription_uuid: str) -> None:
        subscription = next(
            s for s in self.subscriptions if s.uuid == subscription_uuid
        )
        self.subscriptions.remove(subscription)
        self.pubsub.publish('deleted', subscription)


def make_subscription(events=('call_push_notification',), **fields) -> Subscription:
    subscription = Subscription(uuid=str(uuid.uuid4()))
    owner = fields.pop('owner_user_uuid', str(uuid.uuid4()))
    subscription.from_schema(
        name=fields.pop('name', 'test'),
        service=fields.pop('service', 'mobile'),
        events=list(events),
        events_user_uuid=fields.pop('events_user_uuid', owner),
        owner_user_uuid=owner,
        owner_tenant_uuid=fields.pop('owner_tenant_uuid', MASTER_TENANT),
        config=fields.pop('config', {}),
        metadata_=fields.pop('metadata_', {'mobile': 'true'}),
    )
    return subscription


def make_consumer(broker: FakeBroker, clock: FakeClock | None = None) -> BusConsumer:
    consumer = BusConsumer(
        name='wazo_webhookd',
        exchange_name='wazo-headers',
        exchange_type='headers',
        clock=clock or broker.clock,
    )
    consumer.connection = FakeConnection(broker)
    return consumer


def make_handler(consumer: BusConsumer, service: FakeSubscriptionService):
    config: Any = {}
    return SubscriptionBusEventHandler(consumer, config, {}, service)  # type: ignore[arg-type]


def status_of(consumer: BusConsumer) -> dict:
    aggregator = StatusAggregator()
    aggregator.add_provider(consumer.provide_status)
    return json.loads(json.dumps(aggregator.status()))


def wait_until_bound(registrar: SubscriptionRegistrar, expected: int) -> dict:
    def done() -> bool:
        counts = registrar.status()
        return counts['bound'] == counts['desired'] == expected

    with registrar._cond:
        assert registrar._cond.wait_for(done, timeout=20), registrar.status()
    return registrar.status()


@pytest.fixture(autouse=True)
def master_tenant():
    with patch(
        'wazo_webhookd.plugins.subscription.bus.master_tenant_uuid', MASTER_TENANT
    ):
        yield


# Criterion 1


def test_start_with_3500_while_another_thread_creates_20_uses_one_thread_per_connection():
    broker = FakeBroker()
    consumer = make_consumer(broker)
    stored = [make_subscription() for _ in range(3500)]
    created = [make_subscription() for _ in range(20)]
    handler = make_handler(consumer, FakeSubscriptionService(stored))
    registrar_thread = Thread(
        target=consumer._registrar.run, args=(Event(),), daemon=True
    )

    # C1: the start loop runs while the consumer is running
    with patch.object(
        BusConsumer, 'is_running', new_callable=PropertyMock, return_value=True
    ):
        registrar_thread.start()
        start = Thread(target=handler.subscribe)
        create = Thread(
            target=lambda: [handler.on_subscription_created(s) for s in created]
        )
        start.start()
        create.start()
        start.join()
        create.join()
        try:
            counts = wait_until_bound(consumer._registrar, 3520)
        finally:
            consumer._registrar.stop()
            registrar_thread.join(timeout=5)

    assert broker.violations == []
    assert (counts['bound'], counts['desired']) == (3520, 3520)
    assert not registrar_thread.is_alive()


# Criterion 2


def test_external_auth_added_returns_without_amqp_call_then_registrar_binds_it():
    broker = FakeBroker()
    consumer = make_consumer(broker)
    service = FakeSubscriptionService()
    make_handler(consumer, service)
    mobile = MobileService()
    mobile.subscription_service = service  # type: ignore[assignment]

    mobile.on_external_auth_added(
        {'data': {'external_auth_name': 'mobile', 'user_uuid': 'user-1'}},
        {'tenant_uuid': MASTER_TENANT},
    )

    assert broker.frames == 0
    assert len(service.subscriptions) == 1
    consumer._registrar.bind_due()
    assert set(broker.exchange_binds) == set(service.subscriptions[0].events)
    counts = consumer._registrar.status()
    assert (counts['bound'], counts['desired']) == (6, 6)


# Criterion 3


@pytest.mark.parametrize(
    'attempt,rand,expected',
    [
        (1, 0.5, 1.0),
        (2, 0.5, 2.0),
        (3, 0.5, 4.0),
        (6, 0.5, 32.0),
        (7, 0.5, 60.0),
        (40, 0.5, 60.0),
        (1, 0.0, 0.8),
        (1, 1.0, 1.2),
        (7, 0.0, 48.0),
        (7, 1.0, 72.0),
    ],
)
def test_retry_delay_doubles_from_one_second_capped_at_60_with_20_percent_jitter(
    attempt, rand, expected
):
    assert retry_delay(attempt, rand) == pytest.approx(expected)


def make_registrar(broker: FakeBroker, rand=lambda: 0.5) -> SubscriptionRegistrar:
    exchange = WebhookdExchange(
        'wazo_webhookd', 'headers', {}, 'wazo-headers', 'headers'
    )
    return SubscriptionRegistrar(
        exchange, lambda: FakeConnection(broker), clock=broker.clock, rand=rand
    )


def test_failing_bind_is_retried_at_1_2_4_seconds_while_the_others_are_bound():
    broker = FakeBroker()
    registrar = make_registrar(broker)
    broker.bind_failures['b'] = 3
    for name in ('a', 'b', 'c'):
        registrar.add(name)

    registrar.bind_due()
    counts = registrar.status()
    assert (counts['bound'], counts['failed'], counts['pending']) == (2, 1, 0)
    assert registrar.next_retry_in() == pytest.approx(1.0)

    attempts = []
    for at in (0.99, 1.0, 2.99, 3.0, 6.99, 7.0):
        broker.clock.now = at
        before = broker.bind_failures['b'], broker.exchange_binds['b']
        registrar.bind_due()
        attempts.append(
            before != (broker.bind_failures['b'], broker.exchange_binds['b'])
        )

    assert attempts == [False, True, False, True, False, True]
    counts = registrar.status()
    assert (counts['bound'], counts['desired'], counts['failed']) == (3, 3, 0)
    assert counts['retries'] == 3
    assert counts['last_error'] == 'ConnectionResetError'
    assert registrar.next_retry_in() is None
    # each failure renews the connection, and everything is rebound on it
    assert broker.exchange_binds == Counter(a=4, b=1, c=3)


# Criterion 4


def test_consumer_reconnection_marks_everything_unbound_and_rebinds_it():
    broker = FakeBroker()
    consumer = make_consumer(broker)
    consumer.subscribe('a', lambda payload: None)
    consumer.subscribe('b', lambda payload: None)
    consumer._registrar.bind_due()
    assert broker.exchange_binds == Counter(a=1, b=1)

    consumer.get_consumers(lambda **kwargs: kwargs, FakeConnection(broker).channel())

    assert consumer._registrar.status()['bound'] == 0
    consumer._registrar.bind_due()
    assert broker.exchange_binds == Counter(a=2, b=2)
    assert consumer._registrar.status()['bound'] == 2
    assert broker.releases == 1  # the binding connection is renewed too


def test_broker_refusing_connections_for_30_seconds_at_start_ends_fully_bound():
    broker = FakeBroker()
    broker.refuse_until = 30.0
    registrar = make_registrar(broker)
    for name in ('a', 'b', 'c'):
        registrar.add(name)

    rounds = 0
    while registrar.status()['bound'] < 3 and rounds < 20:
        registrar.bind_due()
        delay = registrar.next_retry_in()
        if delay is not None:
            broker.clock.now += delay
        rounds += 1

    counts = registrar.status()
    assert (counts['bound'], counts['desired']) == (3, 3)
    assert 30.0 <= broker.clock.now <= 30.0 + 72.0
    assert counts['last_error'] == 'ConnectionRefusedError'


# Criterion 5


def test_status_counts_and_fail_only_two_minutes_after_start_while_not_all_bound():
    broker = FakeBroker()
    consumer = make_consumer(broker)
    consumer.consumer_connected = lambda: True  # type: ignore[method-assign]
    broker.bind_failures['b'] = 1
    consumer.subscribe('a', lambda payload: None)
    consumer.subscribe('b', lambda payload: None)
    consumer.subscribe('b', lambda payload: 'second handler')
    consumer.subscribe('c', lambda payload: None)

    status = status_of(consumer)['subscriptions']
    assert status == {
        'status': 'ok',
        'desired': 4,
        'bound': 0,
        'pending': 4,
        'failed': 0,
        'retries': 0,
        'last_error': None,
        'last_error_at': None,
        'last_full_bind_at': None,
        'queue_bindings_synced': False,
    }

    consumer._registrar.bind_due()
    status = status_of(consumer)['subscriptions']
    assert (status['bound'], status['failed'], status['pending']) == (2, 2, 0)
    assert status['status'] == 'ok'

    broker.clock.now = 120.0
    assert status_of(consumer)['subscriptions']['status'] == 'ok'
    broker.clock.now = 120.5
    status = status_of(consumer)['subscriptions']
    assert status['status'] == 'fail'
    assert status['last_error'] == 'ConnectionResetError'
    assert status['last_error_at'] is not None

    consumer._registrar.bind_due()
    status = status_of(consumer)['subscriptions']
    assert (status['status'], status['bound'], status['desired']) == ('ok', 4, 4)
    assert status['last_full_bind_at'] is not None


def test_status_grace_restarts_at_consumer_reconnection():
    broker = FakeBroker()
    consumer = make_consumer(broker)
    consumer.subscribe('a', lambda payload: None)
    broker.clock.now = 500.0

    consumer.get_consumers(lambda **kwargs: kwargs, FakeConnection(broker).channel())

    assert status_of(consumer)['subscriptions']['status'] == 'ok'
    broker.clock.now = 620.5
    assert status_of(consumer)['subscriptions']['status'] == 'fail'


def test_removed_subscription_leaves_desired_and_unsubscribed_handler_is_not_counted():
    broker = FakeBroker()
    consumer = make_consumer(broker)
    handler = lambda payload: None  # noqa: E731
    consumer.subscribe('a', handler)
    consumer.subscribe('a', lambda payload: None)

    assert consumer.unsubscribe('a', handler) is True
    assert consumer.unsubscribe('a', handler) is False
    assert consumer._registrar.status()['desired'] == 1
    consumer.unsubscribe('a', consumer._ConsumerMixin__subscriptions['a'][0].handler)
    assert consumer._registrar.status()['desired'] == 0


# Criterion 6


def test_full_bind_log_line_bound_equals_the_database_subscription_event_pairs(caplog):
    broker = FakeBroker()
    consumer = make_consumer(broker)
    stored = [
        make_subscription(events=['call_push_notification']),
        make_subscription(events=['user_missed_call', 'call_push_notification']),
        make_subscription(
            events=[
                'chatd_user_room_message_created',
                'call_push_notification',
                'call_cancel_push_notification',
                'user_voicemail_message_created',
                'global_voicemail_message_created',
                'user_missed_call',
            ]
        ),
    ]
    database_pairs = sum(len(s.events) for s in stored)
    make_handler(consumer, FakeSubscriptionService(stored)).subscribe()
    broker.clock.now = 2.5

    with caplog.at_level(logging.INFO, logger='wazo_webhookd.bus'):
        consumer._registrar.bind_due()

    full = [r.getMessage() for r in caplog.records if 'state=bound' in r.getMessage()]
    assert full == [
        f'webhookd_subscriptions state=bound bound={database_pairs} '
        f'desired={database_pairs} seconds=2.5'
    ]


def test_full_bind_line_is_logged_again_once_the_start_loop_has_loaded_every_row(
    caplog,
):
    # seen in the integration run: the consumer's own handlers are bound
    # before the start loop runs, and rows on already-bound events make no
    # new transition, so the only line said bound=8
    broker = FakeBroker()
    consumer = make_consumer(broker)
    consumer.subscribe('call_push_notification', lambda payload: None)
    consumer._registrar.bind_due()
    stored = [make_subscription(events=['call_push_notification']) for _ in range(5)]

    with caplog.at_level(logging.INFO, logger='wazo_webhookd.bus'):
        make_handler(consumer, FakeSubscriptionService(stored)).subscribe()
        consumer._registrar.bind_due()

    full = [r.getMessage() for r in caplog.records if 'state=bound' in r.getMessage()]
    assert full == ['webhookd_subscriptions state=bound bound=6 desired=6 seconds=0.0']


def test_queue_bindings_synced_only_once_the_broker_holds_every_queue_binding():
    broker = FakeBroker()
    consumer = make_consumer(broker)
    consumer.subscribe('a', lambda payload: None, headers={'user_uuid:u1': True})
    assert status_of(consumer)['subscriptions']['queue_bindings_synced'] is False

    # wazo-bus counts the bindings known at (re)connection as declared by
    # the kombu Consumer; later ones are applied by on_iteration
    consumer.get_consumers(lambda **kwargs: kwargs, FakeConnection(broker).channel())
    consumer.subscribe('b', lambda payload: None, headers={'user_uuid:u2': True})
    consumer.subscribe('c', lambda payload: None, headers={'user_uuid:u3': True})
    broker.queue_bind_failures['c'] = 1
    assert status_of(consumer)['subscriptions']['queue_bindings_synced'] is False

    consumer.on_iteration()
    assert len(broker.queue_bindings) == 1
    assert status_of(consumer)['subscriptions']['queue_bindings_synced'] is False

    consumer.on_iteration()
    assert len(broker.queue_bindings) == 2
    assert status_of(consumer)['subscriptions']['queue_bindings_synced'] is True


# Criterion 7


def test_a_message_handled_for_more_than_60_seconds_makes_bus_consumer_fail():
    clock = FakeClock()
    consumer = make_consumer(FakeBroker(clock))
    consumer.consumer_connected = lambda: True  # type: ignore[method-assign]
    seen = []

    def slow_handler(payload):
        clock.now += 60
        seen.append(status_of(consumer)['bus_consumer'])
        clock.now += 1
        seen.append(status_of(consumer)['bus_consumer'])

    consumer.subscribe('slow', slow_handler)
    assert status_of(consumer)['bus_consumer'] == {
        'status': 'ok',
        'last_message_age_seconds': None,
    }

    clock.now = 10
    consumer._ConsumerMixin__dispatch('slow', {}, {'name': 'slow'})
    clock.now += 5

    assert [s['status'] for s in seen] == ['ok', 'fail']
    assert status_of(consumer)['bus_consumer'] == {
        'status': 'ok',
        'last_message_age_seconds': 5.0,
    }


def test_a_failing_handler_still_ends_the_message():
    clock = FakeClock()
    consumer = make_consumer(FakeBroker(clock))
    consumer.consumer_connected = lambda: True  # type: ignore[method-assign]

    def failing(payload):
        raise RuntimeError('boom')

    consumer.subscribe('boom', failing)
    consumer._ConsumerMixin__dispatch('boom', {}, {'name': 'boom'})
    clock.now = 100

    assert status_of(consumer)['bus_consumer'] == {
        'status': 'ok',
        'last_message_age_seconds': 100.0,
    }


def test_a_dispatch_that_raises_still_ends_the_message():
    # wazo-bus checks the event outside its lock: an unsubscribe in between
    # makes the dispatch raise KeyError, which must not read as a stuck one
    clock = FakeClock()
    consumer = make_consumer(FakeBroker(clock))
    consumer.consumer_connected = lambda: True  # type: ignore[method-assign]

    with pytest.raises(KeyError):
        consumer._ConsumerMixin__dispatch('gone', {}, {'name': 'gone'})
    clock.now = 61

    assert status_of(consumer)['bus_consumer'] == {
        'status': 'ok',
        'last_message_age_seconds': 61.0,
    }


def test_bus_consumer_fails_when_disconnected():
    consumer = make_consumer(FakeBroker())
    consumer.consumer_connected = lambda: False  # type: ignore[method-assign]
    assert status_of(consumer)['bus_consumer']['status'] == 'fail'


# Criterion 10


KEY_VALUE = re.compile(r'^[a-z_]+=\S+$')


def test_registrar_log_lines_are_prefixed_key_value_and_carry_no_secret(caplog):
    broker = FakeBroker()
    consumer = make_consumer(broker)
    broker.bind_failures['b'] = 1
    user_uuid = str(uuid.uuid4())
    consumer.subscribe(
        'a', lambda payload: None, headers={f'user_uuid:{user_uuid}': True}
    )
    consumer.subscribe('b', lambda payload: None)

    # the registrar logs at INFO and above; DEBUG is the consumer's own
    with caplog.at_level(logging.INFO, logger='wazo_webhookd.bus'):
        consumer._registrar.bind_due()
        broker.clock.now = 5
        consumer._registrar.bind_due()
        consumer.get_consumers(
            lambda **kwargs: kwargs, FakeConnection(broker).channel()
        )
        consumer._registrar.bind_due()

    lines = [r.getMessage() for r in caplog.records if r.name == 'wazo_webhookd.bus']
    states = [line.split()[1] for line in lines]
    assert states == [
        'state=retry',
        'state=bound',
        'state=rebind',
        'state=bound',
    ]
    for line in lines:
        assert line.startswith(LOG_PREFIX + ' ')
        assert all(KEY_VALUE.match(pair) for pair in line.split()[1:]), line
        assert SECRET not in line
    assert all(SECRET not in r.getMessage() for r in caplog.records)
    assert user_uuid not in json.dumps(status_of(consumer))


# Lifecycle


def test_registrar_thread_stops_when_asked_while_waiting():
    registrar = make_registrar(FakeBroker())
    ready = Event()
    thread = Thread(target=registrar.run, args=(ready,), daemon=True)
    thread.start()
    assert ready.wait(timeout=5)

    registrar.stop()
    thread.join(timeout=5)

    assert not thread.is_alive()


def test_registrar_releases_its_connection_when_it_stops():
    broker = FakeBroker()
    registrar = make_registrar(broker)
    registrar.add('a')
    registrar.bind_due()

    registrar.stop()
    registrar.run(Event())

    assert broker.releases == 1


def test_a_release_that_raises_is_ignored():
    broker = FakeBroker()
    registrar = make_registrar(broker)
    registrar.add('a')
    registrar.bind_due()

    def broken_release():
        raise OSError('socket already closed')

    registrar._connection.release = broken_release  # type: ignore[union-attr]
    registrar.rebind_all('consumer_connected')
    registrar.bind_due()

    assert broker.exchange_binds == Counter(a=2)


def test_first_full_bind_waits_for_the_start_loop_then_a_full_pass():
    # SR-2: an empty or partial desired set is not the first full bind
    registrar = make_registrar(FakeBroker())
    registrar.bind_due()
    assert not registrar.first_full_bind.is_set()

    registrar.add('a')
    registrar.bind_due()
    assert not registrar.first_full_bind.is_set()

    registrar.add('b')
    registrar.report_next_full_bind()
    assert not registrar.first_full_bind.is_set()
    registrar.bind_due()

    assert registrar.first_full_bind.is_set()


def test_a_bind_in_flight_during_a_reconnection_is_bound_again_after_it():
    # SR-3: the consumer reconnects while the registrar is inside _bind('x')
    broker = FakeBroker()
    registrar = make_registrar(broker)
    registrar.add('x')
    registrar.add('y')
    original = FakeChannel.exchange_bind
    reconnected: list[bool] = []

    def bind_then_reconnect(channel, destination, source, **kwargs):
        original(channel, destination, source, **kwargs)
        if kwargs['arguments']['name'] == 'x' and not reconnected:
            reconnected.append(True)
            registrar.rebind_all('consumer_connected')

    with patch.object(FakeChannel, 'exchange_bind', bind_then_reconnect):
        registrar.bind_due()

    assert broker.exchange_binds == Counter(x=2, y=1)
    assert broker.releases == 1
    counts = registrar.status()
    assert (counts['bound'], counts['desired']) == (2, 2)


def test_a_stop_during_a_broker_outage_ends_the_pass_after_one_attempt():
    # SR-4: each connect may wait its timeout; a stop must not wait for all
    broker = FakeBroker()
    broker.refuse_until = 1e9
    registrar = make_registrar(broker)
    for name in ('a', 'b', 'c'):
        registrar.add(name)
    attempts = []
    original = FakeConnection.connect

    def connect_then_stop(connection):
        attempts.append(1)
        registrar.stop()
        original(connection)

    with patch.object(FakeConnection, 'connect', connect_then_stop):
        registrar.bind_due()

    assert len(attempts) == 1


def test_a_new_event_name_gets_its_own_grace():
    # SR-6: hours after the start, a never-seen event is not late at once
    broker = FakeBroker()
    registrar = make_registrar(broker)
    registrar.add('a')
    registrar.bind_due()
    broker.clock.now = 5000.0
    broker.bind_failures['z'] = 100

    registrar.add('z')
    assert registrar.status()['status'] == 'ok'
    registrar.bind_due()
    assert registrar.status()['status'] == 'ok'

    broker.clock.now = 5120.5
    assert registrar.status()['status'] == 'fail'


def test_the_systemd_unit_stops_in_15_seconds_and_starts_after_rabbitmq():
    # SR-5: the container of the integration test has no systemd
    unit = (Path(__file__).parents[2] / 'debian' / 'wazo-webhookd.service').read_text()
    lines = unit.splitlines()
    assert 'TimeoutStopSec=15' in lines
    assert 'After=network.target rabbitmq-server.service' in lines
    assert 'Wants=rabbitmq-server.service' in lines


def test_bus_consumer_from_config_registers_the_registrar_thread():
    consumer = BusConsumer.from_config(
        {'exchange_name': 'wazo-headers', 'exchange_type': 'headers'}
    )
    names = [t.thread.name for t in consumer._ThreadableMixin__internal_threads_list]
    assert names == ['wazo_webhookd:consumer', 'wazo_webhookd:registrar']
    assert consumer.first_full_bind is consumer._registrar.first_full_bind


def test_start_loop_registers_every_subscription_past_one_that_fails(caplog):
    broker = FakeBroker()
    consumer = make_consumer(broker)
    stored = [make_subscription() for _ in range(3)]
    handler = make_handler(consumer, FakeSubscriptionService(stored))

    with patch(
        'wazo_webhookd.plugins.subscription.bus.SubscriptionBusEventHandler._build_headers',
        side_effect=[{}, ValueError('bad row'), {}],
    ), caplog.at_level(logging.ERROR):
        handler.subscribe()

    assert consumer._registrar.status()['desired'] == 2
    assert [r.getMessage() for r in caplog.records] == [
        f'webhookd_subscriptions state=register_failed subscription={stored[1].uuid}'
        ' error=ValueError'
    ]
