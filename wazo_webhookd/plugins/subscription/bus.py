# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from .schema import subscription_schema

logger = logging.getLogger(__name__)


class SubscriptionBusEventHandler:
    def __init__(self, bus_consumer, service_manager, subscription_service):
        self._bus_consumer = bus_consumer
        self._service = subscription_service
        self._service.pubsub.subscribe("created", self.on_subscription_created)
        self._service.pubsub.subscribe("updated", self.on_subscription_updated)
        self._service.pubsub.subscribe("deleted", self.on_subscription_deleted)
        self._service_manager = service_manager

    def subscribe(self, bus_consumer):
        for subscription in self._service.list():
            self._add_one_subscription_to_bus(subscription)

    def on_subscription_created(self, subscription):
        self._add_one_subscription_to_bus(subscription)

    def on_subscription_updated(self, subscription):
        self._bus_consumer.change_subscription(
            subscription.uuid,
            subscription.events,
            subscription.events_user_uuid,
            subscription.events_wazo_uuid,
            self._make_callback(subscription),
        )

    def on_subscription_deleted(self, subscription):
        self._bus_consumer.unsubscribe_from_event_names(subscription.uuid)

    def _add_one_subscription_to_bus(self, subscription):
        self._bus_consumer.subscribe_to_event_names(
            subscription.uuid,
            subscription.events,
            subscription.events_user_uuid,
            subscription.events_wazo_uuid,
            self._make_callback(subscription),
        )

    def _make_callback(self, subscription):
        try:
            service = self._service_manager[subscription.service]
        except KeyError:
            logger.error(
                '%s: no such service plugin. Subscription "%s" disabled',
                subscription.service,
                subscription.name,
            )
            return

        subscription = subscription_schema.dump(subscription).data

        def callback(body, _):
            service.obj.callback().apply_async([subscription, body])

        return callback
