# Copyright 2017-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
import random
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from inspect import signature
from threading import Condition, Event, Lock
from time import monotonic
from typing import TYPE_CHECKING, Any

import kombu
from wazo_bus.base import Base
from wazo_bus.mixins import ConsumerMixin, ThreadableMixin
from wazo_bus.publisher import BusPublisher as BasePublisher
from xivo.status import Status

if TYPE_CHECKING:
    from amqp import Message
    from kombu.transport.base import StdChannel
    from xivo.status import StatusDict

    Payload = dict[str, Any]
    Headers = dict[str, Any]
    AmpqCallback = Callable[[dict[str, Any], Message | None], None]

logger = logging.getLogger(__name__)

LOG_PREFIX = 'webhookd_subscriptions'
RETRY_FIRST_DELAY = 1.0
RETRY_MAX_DELAY = 60.0
RETRY_JITTER = 0.2
FULL_BIND_GRACE = 120.0
MESSAGE_STUCK_AFTER = 60.0


def _wants_headers(handler: Callable) -> bool:
    return len(signature(handler).parameters) == 2


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def retry_delay(attempt: int, rand: float) -> float:
    """1 s, doubling, capped at 60 s, then ±20 % (`rand` in [0, 1])."""
    base = min(RETRY_MAX_DELAY, RETRY_FIRST_DELAY * 2 ** min(attempt - 1, 16))
    return base * (1 + RETRY_JITTER * (2 * rand - 1))


# !!DO NOT RENAME!!
# Must be the same name to allow remapping of private (mangled) methods
class _ConsumerMixin(ConsumerMixin):
    """This wrapper allows routing events from the same queue to different
    callbacks, based on the AMQP headers of the message.
    This is a performance optimization to avoid having many queues in RabbitMQ
    for wazo-webhookd."""

    _clock: Callable[[], float] = monotonic
    _message_started_at: float | None = None
    _message_ended_at: float | None = None

    def _check_headers_match(
        self, headers: Headers | None, binding: kombu.binding
    ) -> bool:
        # only perform check if exchange type is headers
        if self._exchange.type != 'headers':
            return True
        compare = all if binding.arguments.get('x-match', 'all') == 'all' else any
        headers = {k: v for k, v in headers.items() if not k.startswith('x-')}  # type: ignore
        arguments = {
            k: v for k, v in binding.arguments.items() if not k.startswith('x-')
        }

        return compare([k in headers and headers[k] == v for k, v in arguments.items()])

    def __dispatch(
        self, event_name: str, payload: Payload, headers: Headers | None = None
    ) -> None:
        # Handlers run in turn on the consumer thread: one that never returns
        # stops every push. /status reads these two to say so.
        self._message_started_at = self._clock()
        try:
            self.__dispatch_to_handlers(event_name, payload, headers)
        finally:
            self._message_ended_at = self._clock()
            self._message_started_at = None

    def __dispatch_to_handlers(
        self, event_name: str, payload: Payload, headers: Headers | None
    ) -> None:
        with self.__lock:
            subscriptions = self.__subscriptions[event_name].copy()
        for handler, binding in subscriptions:
            if not self._check_headers_match(headers, binding):
                continue
            try:
                if _wants_headers(handler):
                    self.log.debug(
                        'dispatching event %s to handler %s with headers',
                        event_name,
                        getattr(handler, '__name__', str(handler)),
                    )
                    handler(payload, headers)
                else:
                    handler(payload)
            except Exception:
                self.log.exception(
                    'Handler \'%s\' for event \'%s\' failed',
                    getattr(handler, '__name__', handler),
                    event_name,
                )
            continue


class BusConsumer(ThreadableMixin, _ConsumerMixin, Base):
    def __init__(
        self,
        name='',
        exchange_name: str = '',
        exchange_type: str = '',
        clock: Callable[[], float] = monotonic,
        **kwargs: Any,
    ) -> None:
        exchange_kwargs = {'auto_delete': True}
        self._webhookd_exchange = WebhookdExchange(
            name,
            exchange_type,
            exchange_kwargs,
            exchange_name,
            exchange_type,
        )
        super().__init__(
            name=name,
            exchange_name=self._webhookd_exchange.name,
            exchange_type=exchange_type,
            exchange_kwargs=exchange_kwargs,
            **kwargs,
        )
        self._clock = clock
        self._registrar = SubscriptionRegistrar(
            self._webhookd_exchange, lambda: self.connection.clone(), clock=clock
        )
        self._register_thread('registrar', self._registrar.run, self._registrar.stop)
        self._handlers_lock = Lock()
        self._handlers: dict[
            str, tuple[AmpqCallback, Sequence[str], Headers | None]
        ] = {}

    @property
    def first_full_bind(self) -> Event:
        return self._registrar.first_full_bind

    # Never an AMQP call: any thread may subscribe, the consumer's own
    # included (BUG-646). wazo-bus records the queue binding under its lock
    # and applies it from the consumer thread; the registrar binds the
    # exchange.
    def subscribe(self, event_name: str, *args, **kwargs) -> None:
        super().subscribe(event_name, *args, **kwargs)
        self._registrar.add(event_name)

    def unsubscribe(self, event_name: str, *args, **kwargs) -> bool:
        removed = super().unsubscribe(event_name, *args, **kwargs)
        if removed:
            self._registrar.remove(event_name)
        return removed

    def get_consumers(
        self, Consumer: kombu.Consumer, channel: StdChannel
    ) -> list[kombu.Consumer]:
        self._webhookd_exchange.declare(channel)
        # the auto-delete exchange and its bindings may be gone with the queue
        self._registrar.rebind_all('consumer_connected')
        return super().get_consumers(Consumer, channel)

    # Deprecated, wrapper for plugin compatibility
    # please use method `subscribe`
    def subscribe_to_event_names(
        self,
        uuid: str | None,
        event_names: Sequence[str],
        user_uuid: str,
        wazo_uuid: str,
        callback: AmpqCallback,
    ) -> None:
        if uuid is None:
            raise RuntimeError('uuid must be set')
        if not event_names:
            logger.warning('subscription `%s` doesn\'t have event_names set', uuid)
            return

        # arg1 = payload
        # arg2 = message object from libamqp
        two_arg_callback = callback

        def one_arg_callback(payload: dict[str, Any]) -> None:
            return two_arg_callback(payload, None)

        headers: dict[str, str | bool] = {
            'x-internal': True,
        }
        if user_uuid:
            headers[f'user_uuid:{user_uuid}'] = True
        if wazo_uuid:
            headers['origin_uuid'] = str(wazo_uuid)

        for event in event_names:
            self.subscribe(
                event, one_arg_callback, headers=headers, headers_match_all=True
            )

        with self._handlers_lock:
            self._handlers[uuid] = (callback, event_names, headers)

    # Deprecated, wrapper for plugin compatibility
    # Please use method `unsubscribe`
    def unsubscribe_from_event_names(self, uuid: str) -> None:
        with self._handlers_lock:
            callback, events, _ = self._handlers.pop(uuid)
        for event in events:
            self.unsubscribe(event, callback)

    def provide_status(self, status: StatusDict) -> None:
        now = self._clock()
        started, ended = self._message_started_at, self._message_ended_at
        stuck = started is not None and now - started > MESSAGE_STUCK_AFTER
        connected = self.consumer_connected()
        status['bus_consumer']['status'] = (
            Status.ok if connected and not stuck else Status.fail
        )
        status['bus_consumer']['last_message_age_seconds'] = (
            None if ended is None else round(now - ended, 1)
        )
        status['subscriptions'].update(
            self._registrar.status(),
            queue_bindings_synced=self.wait_synchronized(timeout=0),
        )

    @classmethod
    def from_config(cls, bus_config):
        return cls(name='wazo_webhookd', **bus_config)


class BusPublisher(BasePublisher):
    @classmethod
    def from_config(cls, service_uuid, bus_config):
        return cls(name='wazo-webhookd', service_uuid=service_uuid, **bus_config)


class WebhookdExchange:
    def __init__(
        self,
        name: str,
        type_: str,
        kwargs: dict[str, Any],
        upstream_exchange_name: str,
        upstream_exchange_type: str,
    ):
        self.name = name
        self._kombu_exchange = kombu.Exchange(name, type_, **kwargs)
        self._upstream_kombu_exchange = kombu.Exchange(
            upstream_exchange_name, upstream_exchange_type
        )

    def declare(self, channel: StdChannel) -> None:
        logger.debug('Declaring exchange %s', self._kombu_exchange.name)
        self._kombu_exchange.declare(channel=channel)

    def bind(self, event_name: str, channel: StdChannel) -> None:
        # declared again: the exchange is auto-delete and may have gone
        self._kombu_exchange.declare(channel=channel)
        headers = {'name': event_name}
        binding = kombu.binding(self._upstream_kombu_exchange, None, headers, headers)
        binding.bind(self._kombu_exchange, channel=channel)


class SubscriptionRegistrar:
    """The only code that binds webhookd's exchange at the broker.

    A py-amqp connection serves one thread (BUG-646): every other thread
    changes the desired set under the lock and wakes this one, which owns its
    connection, binds what is missing one event at a time, retries a failure
    with backoff without stopping the others, and rebinds everything after a
    reconnection (bindings are idempotent at the broker).

    Counts are (handler, event) pairs: one per subscription event, plus
    webhookd's own handlers (user/tenant deleted, mobile external auth).
    """

    def __init__(
        self,
        exchange: WebhookdExchange,
        connect: Callable[[], kombu.Connection],
        clock: Callable[[], float] = monotonic,
        rand: Callable[[], float] = random.random,
        wall: Callable[[], str] = _utcnow,
    ) -> None:
        self._exchange = exchange
        self._connect = connect
        self._clock, self._rand, self._wall = clock, rand, wall
        self._cond = Condition()
        self._desired: Counter[str] = Counter()
        self._bound: set[str] = set()
        self._failures: dict[str, int] = {}
        self._retry_at: dict[str, float] = {}
        self._retries = 0
        self._last_error: str | None = None
        self._last_error_at: str | None = None
        self._last_full_bind_at: str | None = None
        self._unbound_since = clock()
        self._full = False
        self._drop_connection = False
        self._stopping = False
        self._connection: kombu.Connection | None = None
        self.first_full_bind = Event()

    def add(self, event_name: str) -> None:
        with self._cond:
            self._desired[event_name] += 1
            self._cond.notify_all()

    def remove(self, event_name: str) -> None:
        # the exchange binding stays: the queue binding wazo-bus removes is
        # what stops delivery
        with self._cond:
            self._desired[event_name] -= 1
            if self._desired[event_name] <= 0:
                del self._desired[event_name]

    def rebind_all(self, reason: str) -> None:
        with self._cond:
            self._bound.clear()
            self._unbound_since = self._clock()
            self._full = False
            self._drop_connection = True
            logger.info(
                '%s state=rebind reason=%s desired=%d',
                LOG_PREFIX,
                reason,
                sum(self._desired.values()),
            )
            self._cond.notify_all()

    def stop(self) -> None:
        with self._cond:
            self._stopping = True
            self._cond.notify_all()

    def run(self, ready_flag: Event) -> None:
        ready_flag.set()
        while not self._stopping:
            self.bind_due()
            with self._cond:
                if not self._stopping and not self._due():
                    self._cond.wait(self.next_retry_in())
        self._release()

    def next_retry_in(self) -> float | None:
        with self._cond:
            waiting = [
                at for event, at in self._retry_at.items() if event in self._desired
            ]
            return max(0.0, min(waiting) - self._clock()) if waiting else None

    def bind_due(self) -> None:
        while not self._stopping:
            with self._cond:
                drop, self._drop_connection = self._drop_connection, False
                due = self._due()
            if drop:
                self._release()
            if not due:
                break
            for event_name in due:
                try:
                    self._bind(event_name)
                except Exception as exc:
                    self._release()
                    self._failed(event_name, exc)
                else:
                    self._succeeded(event_name)
        self._check_full()

    def status(self) -> dict[str, Any]:
        with self._cond:
            desired = sum(self._desired.values())
            bound = sum(n for e, n in self._desired.items() if e in self._bound)
            failed = sum(
                n
                for e, n in self._desired.items()
                if e not in self._bound and e in self._failures
            )
            late = self._clock() - self._unbound_since > FULL_BIND_GRACE
            return {
                'status': Status.fail if bound < desired and late else Status.ok,
                'desired': desired,
                'bound': bound,
                'pending': desired - bound - failed,
                'failed': failed,
                'retries': self._retries,
                'last_error': self._last_error,
                'last_error_at': self._last_error_at,
                'last_full_bind_at': self._last_full_bind_at,
            }

    def _due(self) -> list[str]:
        now = self._clock()
        return [
            event
            for event in self._desired
            if event not in self._bound and self._retry_at.get(event, 0.0) <= now
        ]

    def _bind(self, event_name: str) -> None:
        if self._connection is None:
            self._connection = self._connect()
        if not self._connection.connected:
            self._connection.connect()
        self._exchange.bind(event_name, self._connection.default_channel)

    def _release(self) -> None:
        if self._connection is None:
            return
        try:
            self._connection.release()
        except Exception as exc:
            logger.debug(
                '%s state=release_failed error=%s', LOG_PREFIX, type(exc).__name__
            )
        self._connection = None

    def _succeeded(self, event_name: str) -> None:
        with self._cond:
            self._bound.add(event_name)
            self._failures.pop(event_name, None)
            self._retry_at.pop(event_name, None)

    def _failed(self, event_name: str, exc: Exception) -> None:
        # the connection is renewed, so everything is rebound on it (scope 3);
        # the exception's text is never logged: it can carry the broker URL
        with self._cond:
            attempt = self._failures.get(event_name, 0) + 1
            delay = retry_delay(attempt, self._rand())
            self._failures[event_name] = attempt
            self._retry_at[event_name] = self._clock() + delay
            self._retries += 1
            self._last_error = type(exc).__name__
            self._last_error_at = self._wall()
            self._bound.clear()
            self._full = False
            logger.warning(
                '%s state=retry event=%s attempt=%d delay=%.1f error=%s',
                LOG_PREFIX,
                event_name,
                attempt,
                delay,
                self._last_error,
            )

    def _check_full(self) -> None:
        with self._cond:
            full = all(event in self._bound for event in self._desired)
            if full and not self._full:
                desired = sum(self._desired.values())
                self._last_full_bind_at = self._wall()
                logger.info(
                    '%s state=bound bound=%d desired=%d seconds=%.1f',
                    LOG_PREFIX,
                    desired,
                    desired,
                    self._clock() - self._unbound_since,
                )
                self.first_full_bind.set()
            self._full = full
            self._cond.notify_all()
