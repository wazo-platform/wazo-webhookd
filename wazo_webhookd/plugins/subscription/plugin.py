# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from .resource import SubscriptionResource
from .resource import SubscriptionsResource
from .service import SubscriptionService


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        config = dependencies['config']
        service = SubscriptionService(config)
        api.add_resource(SubscriptionsResource, '/subscriptions', resource_class_args=[service])
        api.add_resource(SubscriptionResource, '/subscriptions/<subscription_id>', resource_class_args=[service])
