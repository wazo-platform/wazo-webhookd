# Copyright 2017-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from threading import Lock
from typing import TYPE_CHECKING, Any, Union

from wazo_bus.base import Base
from wazo_bus.mixins import ConsumerMixin, ThreadableMixin

if TYPE_CHECKING:
    from amqp import Message

    Payload = dict[str, Any]
    Headers = dict[str, Any]
    AmpqCallback = Callable[[dict[str, Any], Union[Message, None]], None]

logger = logging.getLogger(__name__)


# !!DO NOT RENAME!!
# Must be the same name to allow remapping of private (mangled) methods
class _ConsumerMixin(ConsumerMixin):
    """This wrapper allows routing events from the same queue to different
    callbacks, based on the AMQP headers of the message.
    This is a performance optimization to avoid having many queues in RabbitMQ
    for wazo-webhookd."""

    def _check_headers_match(self, headers: Headers | None, binding) -> bool:
        # only perform check if exchange type is headers
        if self.__exchange.type != 'headers':
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
                handler(payload)
            except Exception:
                self.log.exception(
                    'Handler \'%s\' for event \'%s\' failed',
                    getattr(handler, '__name__', handler),
                    event_name,
                )
            continue


class BusConsumer(ThreadableMixin, _ConsumerMixin, Base):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._handlers_lock = Lock()
        self._handlers: dict[
            str, tuple[AmpqCallback, Sequence[str], Headers | None]
        ] = {}

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

        def one_arg_callback(payload: dict[str, Any]):
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
