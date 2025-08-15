# Copyright 2017-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from xivo.pubsub import CallbackCollector

from .bus import SubscriptionBusEventHandler
from .http import (
    SubscriptionLogsResource,
    SubscriptionResource,
    SubscriptionsResource,
    UserSubscriptionResource,
    UserSubscriptionsResource,
)
from .notifier import SubscriptionNotifier
from .service import SubscriptionService

if TYPE_CHECKING:
    from ...types import PluginDependencyDict


class Plugin:
    def load(self, dependencies: PluginDependencyDict) -> None:
        api = dependencies['api']
        bus_consumer = dependencies['bus_consumer']
        bus_publisher = dependencies['bus_publisher']
        config = dependencies['config']
        service_manager = dependencies['service_manager']
        subscribe_to_next_token_change = dependencies['next_token_change_subscribe']

        master_tenant_callback_collector = CallbackCollector()
        subscribe_to_next_token_change(master_tenant_callback_collector.new_source())

        service = SubscriptionService(config, SubscriptionNotifier(bus_publisher))
        service.subscribe_bus(bus_consumer)

        api.add_resource(
            SubscriptionsResource, '/subscriptions', resource_class_args=[service]
        )
        api.add_resource(
            SubscriptionResource,
            '/subscriptions/<subscription_uuid>',
            resource_class_args=[service],
        )
        api.add_resource(
            UserSubscriptionsResource,
            '/users/me/subscriptions',
            resource_class_args=[service],
        )
        api.add_resource(
            UserSubscriptionResource,
            '/users/me/subscriptions/<subscription_uuid>',
            resource_class_args=[service],
        )
        api.add_resource(
            SubscriptionLogsResource,
            '/subscriptions/<subscription_uuid>/logs',
            resource_class_args=[service],
        )

        bus_handler = SubscriptionBusEventHandler(
            bus_consumer, config, service_manager, service
        )
        master_tenant_callback_collector.subscribe(bus_handler.subscribe)
