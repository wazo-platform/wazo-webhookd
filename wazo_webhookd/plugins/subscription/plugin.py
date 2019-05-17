# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_auth_client import Client as AuthClient

from .bus import SubscriptionBusEventHandler
from .resource import SubscriptionResource
from .resource import SubscriptionsResource
from .resource import UserSubscriptionsResource
from .resource import UserSubscriptionResource
from .service import SubscriptionService


class Plugin(object):
    def load(self, dependencies):
        api = dependencies['api']
        bus_consumer = dependencies['bus_consumer']
        config = dependencies['config']
        service_manager = dependencies['service_manager']

        auth_client = AuthClient(**config['auth'])
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
            resource_class_args=[auth_client, service],
        )
        api.add_resource(
            UserSubscriptionResource,
            '/users/me/subscriptions/<subscription_uuid>',
            resource_class_args=[auth_client, service],
        )

        SubscriptionBusEventHandler(bus_consumer, service_manager, service).subscribe(
            bus_consumer
        )
