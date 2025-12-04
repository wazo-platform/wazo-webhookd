# Copyright 2017-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from inspect import signature
from threading import Lock
from typing import TYPE_CHECKING, Any

import kombu
from wazo_bus.base import Base
from wazo_bus.mixins import ConsumerMixin, ThreadableMixin
from wazo_bus.publisher import BusPublisher as BasePublisher

if TYPE_CHECKING:
    from amqp import Message
    from kombu.transport.base import StdChannel

    Payload = dict[str, Any]
    Headers = dict[str, Any]
    AmpqCallback = Callable[[dict[str, Any], Message | None], None]

logger = logging.getLogger(__name__)


def _wants_headers(handler: Callable) -> bool:
    return len(signature(handler).parameters) == 2


# !!DO NOT RENAME!!
# Must be the same name to allow remapping of private (mangled) methods
class _ConsumerMixin(ConsumerMixin):
    """This wrapper allows routing events from the same queue to different
    callbacks, based on the AMQP headers of the message.
    This is a performance optimization to avoid having many queues in RabbitMQ
    for wazo-webhookd."""

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
        self, name='', exchange_name: str = '', exchange_type: str = '', **kwargs: Any
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
        self._handlers_lock = Lock()
        self._handlers: dict[
            str, tuple[AmpqCallback, Sequence[str], Headers | None]
        ] = {}

    def subscribe(self, event_name: str, *args, **kwargs) -> None:
        if self.is_running:
            self._webhookd_exchange.subscribe_connected(event_name, self.connection)
        else:
            self._webhookd_exchange.subscribe(event_name)
        return super().subscribe(event_name, *args, **kwargs)

    def get_consumers(
        self, Consumer: kombu.Consumer, channel: StdChannel
    ) -> list[kombu.Consumer]:
        self._webhookd_exchange.declare(channel)
        return super().get_consumers(Consumer, channel)

    def on_connection_error(self, exc: Exception, interval: str) -> None:
        self._webhookd_exchange.on_connection_error()
        return super().on_connection_error(exc, interval)

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
        # We need to keep a binding list in case we're not connected yet
        # and to recreate the bindings after rabbitmq restart, as bindings
        # on auto-delete exchanges are not kept in rabbitmq
        self._bindings: set[kombu.binding] = set()
        self._connection: kombu.Connection = None

    def subscribe(self, event_name: str) -> None:
        binding = self._binding(event_name)
        self._bindings.add(binding)

    def subscribe_connected(
        self, event_name: str, consumer_connection: kombu.Connection
    ) -> None:
        if self._connection is None:
            self._connection = consumer_connection.clone()

        if not self._connection.connected:
            self._connection.connect()

        channel = self._connection.default_channel
        self._kombu_exchange.declare(channel=channel)
        binding = self._binding(event_name)
        logger.debug(
            'Binding exchange %s to event %s', self._kombu_exchange.name, event_name
        )
        binding.bind(self._kombu_exchange, channel=channel)
        self._bindings.add(binding)

    def declare(self, channel: StdChannel) -> None:
        logger.debug('Declaring exchange %s', self._kombu_exchange.name)
        self._kombu_exchange.declare(channel=channel)
        logger.debug('Binding exchange %s', self._kombu_exchange.name)
        for binding in self._bindings:
            binding.bind(self._kombu_exchange, channel=channel)

    def on_connection_error(self) -> None:
        if self._connection is None:
            return

        self._connection.release()

    def _binding(self, event_name: str) -> kombu.binding:
        headers = {'name': event_name}
        return kombu.binding(self._upstream_kombu_exchange, None, headers, headers)
