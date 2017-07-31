# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from . import celery_tasks
from .bus import SubscriptionBusEventHandler
from .resource import SubscriptionResource
from .resource import SubscriptionsResource
from .service import SubscriptionService


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        bus_consumer = dependencies['bus_consumer']
        celery_app = dependencies['celery']
        config = dependencies['config']

        service = SubscriptionService(config)
        api.add_resource(SubscriptionsResource, '/subscriptions', resource_class_args=[service])
        api.add_resource(SubscriptionResource, '/subscriptions/<subscription_uuid>', resource_class_args=[service])
        celery_tasks.load(celery_app)
        SubscriptionBusEventHandler(celery_app, service).subscribe(bus_consumer)
