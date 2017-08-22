# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from .bus import SubscriptionBusEventHandler
from .resource import SubscriptionResource
from .resource import SubscriptionsResource
from .service import SubscriptionService


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        bus_consumer = dependencies['bus_consumer']
        config = dependencies['config']
        service_manager = dependencies['service_manager']

        service = SubscriptionService(config)
        api.add_resource(SubscriptionsResource, '/subscriptions', resource_class_args=[service])
        api.add_resource(SubscriptionResource, '/subscriptions/<subscription_uuid>', resource_class_args=[service])
        SubscriptionBusEventHandler(bus_consumer, service_manager, service).subscribe(bus_consumer)
