# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

logger = logging.getLogger(__name__)


class SubscriptionBusEventHandler:

    def __init__(self, bus_consumer, service_manager, subscription_service):
        self._bus_consumer = bus_consumer
        self._service = subscription_service
        self._service.pubsub.subscribe('created', self.on_subscription_created)
        self._service_manager = service_manager
        self._is_subscribed = False

    def subscribe(self, bus_consumer):
        if self._service.list():
            self.subscribe_once()

    def on_subscription_created(self, _):
        self.subscribe_once()

    def subscribe_once(self):
        if not self._is_subscribed:
            logger.debug('Subscribing to all events...')
            self._is_subscribed = True
            self._bus_consumer.subscribe_to_all_events(self.on_wazo_event)

    def on_wazo_event(self, event):
        for subscription in self._service.list():
            if event['name'] in subscription.events:
                try:
                    service = self._service_manager[subscription.service]
                except KeyError:
                    continue
                service.obj.callback().apply_async([subscription.config, event])
