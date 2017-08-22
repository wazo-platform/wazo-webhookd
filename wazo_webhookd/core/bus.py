# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging
import kombu
import kombu.mixins

from xivo.pubsub import Pubsub

logger = logging.getLogger(__name__)


class CoreBusConsumer(kombu.mixins.ConsumerMixin):

    def __init__(self, global_config):
        self._all_events_pubsub = Pubsub()
        self._is_running = False
        self.connection = None

        self._bus_url = 'amqp://{username}:{password}@{host}:{port}//'.format(**global_config['bus'])
        self._exchange = kombu.Exchange(global_config['bus']['exchange_name'],
                                        type=global_config['bus']['exchange_type'])
        self._queue = kombu.Queue('webhookd-wazo-events', auto_delete=True)

    def run(self):
        logger.info("Running bus consumer")
        with kombu.Connection(self._bus_url) as connection:
            self.connection = connection

            super(CoreBusConsumer, self).run()

    def get_consumers(self, Consumer, channel):
        self._exchange.bind(channel).declare()
        return [
            Consumer(self._queue, callbacks=[self._on_bus_message])
        ]

    def on_connection_error(self, exc, interval):
        super(CoreBusConsumer, self).on_connection_error(exc, interval)
        self._is_running = False

    def on_connection_revived(self):
        super(CoreBusConsumer, self).on_connection_revived()
        self._is_running = True

    def is_running(self):
        return self._is_running

    def subscribe_to_all_events(self, callback):
        self._ensure_binding()
        self._all_events_pubsub.subscribe('all_events', callback)

    def _ensure_binding(self):
        if self.connection:
            with self.connection.channel() as channel:
                self._queue.bind(channel).bind_to(self._exchange, routing_key='#')
        else:
            self._queue.bindings.add(kombu.binding(self._exchange, routing_key='#'))

    def _on_bus_message(self, body, message):
        event = body
        self._all_events_pubsub.publish('all_events', event)
        message.ack()
