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

    def subscribe(self, bus_consumer):
        for subscription in self._service.list():
            self._add_one_subscription_to_bus(subscription)

    def on_subscription_created(self, subscription):
        self._add_one_subscription_to_bus(subscription)

    def _add_one_subscription_to_bus(self, subscription):
        try:
            service = self._service_manager[subscription.service]
        except KeyError:
            logger.error('%s: no such service plugin. Subscription "%s" disabled',
                         subscription.service,
                         subscription.name)
        config = dict(subscription.config)

        def callback(body, _):
            service.obj.callback().apply_async([config, body])

        self._bus_consumer.subscribe_to_event_names(subscription.events, callback)
