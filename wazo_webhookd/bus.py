# Copyright 2017-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from collections.abc import Callable
from inspect import signature
from typing import TYPE_CHECKING, Any

import kombu
from wazo_bus.base import Base
from wazo_bus.mixins import ConsumerMixin, ThreadableMixin, headers_match
from wazo_bus.publisher import BusPublisher as BasePublisher
from xivo.status import Status

if TYPE_CHECKING:
    from xivo.status import StatusDict

    Payload = dict[str, Any]
    Headers = dict[str, Any]

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
        # NOTE: the queue binding is shared by event name and tenant (bind_keys),
        # so the subscription's own headers are compared here, as RabbitMQ would
        # (wazo_bus.mixins.headers_match); bind_keys already refuses an exchange
        # other than headers
        return headers_match(headers or {}, binding.arguments)

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
        super().__init__(
            name=name,
            exchange_name=name,
            exchange_type=exchange_type,
            upstream_exchange_name=exchange_name,
            bind_keys=('tenant_uuid',),
            **kwargs,
        )

    def provide_status(self, status: StatusDict) -> None:
        healthy = self.consumer_connected() and not self.consumer_bindings_failing()
        status['bus_consumer']['status'] = Status.ok if healthy else Status.fail

    @classmethod
    def from_config(cls, bus_config):
        return cls(name='wazo_webhookd', **bus_config)


class BusPublisher(BasePublisher):
    @classmethod
    def from_config(cls, service_uuid, bus_config):
        return cls(name='wazo-webhookd', service_uuid=service_uuid, **bus_config)
