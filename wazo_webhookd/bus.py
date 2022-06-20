# Copyright 2017-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from functools import partial
from threading import Lock
from six import iteritems

from xivo_bus.base import Base
from xivo_bus.mixins import ThreadableMixin, ConsumerMixin


logger = logging.getLogger(__name__)


# !!DO NOT RENAME!!
# Must be the same name to allow remapping of private (mangled) methods
class _ConsumerMixin(ConsumerMixin):
    '''This wrapper allows routing events from the same queue to different
    callbacks, based on the AMQP headers of the message.
    This is a performance optimization to avoid having many queues in RabbitMQ
    for wazo-webhookd.'''

    def __check_headers_match(self, headers, binding):
        # only perform check if exchange type is headers
        if self.__exchange.type != 'headers':
            return True
        compare = all if binding.arguments.get('x-match', 'all') == 'all' else any
        headers = {k: v for k, v in iteritems(headers) if not k.startswith('x-')}
        arguments = {
            k: v for k, v in iteritems(binding.arguments) if not k.startswith('x-')
        }

        return compare(
            [k in headers and headers[k] == v for k, v in iteritems(arguments)]
        )

    def __dispatch(self, event_name, payload, headers=None):
        with self.__lock:
            subscriptions = self.__subscriptions[event_name].copy()
        for (handler, binding) in subscriptions:
            if not self.__check_headers_match(headers, binding):
                continue
            try:
                handler(payload)
            except Exception:
                self.log.exception(
                    'Handler \'%s\' for event \'%s\' failed',
                    handler.__name__,
                    event_name,
                )
            continue


class BusConsumer(ThreadableMixin, _ConsumerMixin, Base):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__handlers_lock = Lock()
        self.__handlers = {}

    @staticmethod
    def __compatibility_handler(callback, payload):
        callback(payload, None)

    # Deprecated, wrapper for plugin compatibility
    # please use method `subscribe`
    def subscribe_to_event_names(
        self, uuid, event_names, user_uuid, wazo_uuid, callback
    ):
        if uuid is None:
            raise RuntimeError('uuid must be set')
        if not event_names:
            logger.warning('subscription `%s` doesn\'t have event_names set', uuid)
            return

        callback = partial(self.__compatibility_handler, callback)

        headers = {
            'x-internal': True,
        }
        if user_uuid:
            headers['user_uuid:{}'.format(user_uuid)] = True
        if wazo_uuid:
            headers['origin_uuid'] = str(wazo_uuid)

        for event in event_names:
            self.subscribe(event, callback, headers=headers, headers_match_all=True)

        with self.__handlers_lock:
            self.__handlers[uuid] = (callback, event_names, headers)

    # Deprecated, wrapper for plugin compability
    # Please use method `unsubscribe`
    def unsubscribe_from_event_names(self, uuid):
        with self.__handlers_lock:
            callback, events, _ = self.__handlers.pop(uuid)
        for event in events:
            self.unsubscribe(event, callback)
