# Copyright 2017-2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from .bus import SubscriptionBusEventHandler
from .http import (
    SubscriptionResource,
    SubscriptionsResource,
    UserSubscriptionsResource,
    UserSubscriptionResource,
    SubscriptionLogsResource,
)
from .service import SubscriptionService


class Plugin:
    def load(self, dependencies):
        api = dependencies['api']
        bus_consumer = dependencies['bus_consumer']
        config = dependencies['config']
        service_manager = dependencies['service_manager']

        service = SubscriptionService(config)

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

        SubscriptionBusEventHandler(
            bus_consumer, config, service_manager, service
        ).subscribe(bus_consumer)
