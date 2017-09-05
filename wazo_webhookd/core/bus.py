# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging
import kombu
import kombu.mixins
import threading

from contextlib import contextmanager
from werkzeug.datastructures import MultiDict
from xivo.pubsub import Pubsub

logger = logging.getLogger(__name__)


class CoreBusConsumer(kombu.mixins.ConsumerMixin):

    def __init__(self, global_config):
        self._all_events_pubsub = Pubsub()
        self._is_running = False
        self.connection = None

        self._bus_url = 'amqp://{username}:{password}@{host}:{port}//'.format(**global_config['bus'])
        self._upstream_exchange = kombu.Exchange(global_config['bus']['exchange_name'],
                                                 type=global_config['bus']['exchange_type'])
        self._exchange = kombu.Exchange(global_config['bus']['exchange_headers_name'],
                                        type='headers')
        self._new_consumers = {}
        self._new_consumers_lock = threading.Lock()

    def run(self):
        logger.info("Running bus consumer")
        with kombu.Connection(self._bus_url) as connection:
            self.connection = connection

            super(CoreBusConsumer, self).run()

    def get_consumers(self, Consumer, channel):
        return []

    def on_connection_error(self, exc, interval):
        super(CoreBusConsumer, self).on_connection_error(exc, interval)
        self._is_running = False

    def on_connection_revived(self):
        super(CoreBusConsumer, self).on_connection_revived()
        self._is_running = True

    @contextmanager
    def extra_context(self, connection, channel):
        self._active_connection = connection
        self._upstream_exchange.bind(connection).declare()
        exchange = self._exchange.bind(connection)
        exchange.declare()
        exchange.bind_to(self._upstream_exchange, routing_key='#')
        yield

    def on_iteration(self):
        with self._new_consumers_lock:
            for event_names, callback in self._new_consumers.items():
                logger.debug('Adding consumer for events %s', event_names)

                binding_args = MultiDict()
                binding_args['x-match'] = 'any'
                for event_name in event_names:
                    binding_args['name'] = event_name
                queue = kombu.Queue(channel=self._active_connection,
                                    exclusive=True,
                                    exchange=self._exchange,
                                    binding_arguments=binding_args)
                consumer = kombu.Consumer(channel=self._active_connection,
                                          queues=queue,
                                          callbacks=[callback])
                consumer.consume()
            self._new_consumers = {}

    def is_running(self):
        return self._is_running

    def subscribe_to_event_names(self, event_names, callback):
        logger.debug('Subscribing new callback to events %s', event_names)
        self._new_consumers_lock.acquire()
        self._new_consumers[tuple(event_names)] = callback
        self._new_consumers_lock.release()
