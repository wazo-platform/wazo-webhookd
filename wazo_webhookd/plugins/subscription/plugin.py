# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from .resource import SubscriptionResource
from .service import SubscriptionService


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        config = dependencies['config']
        service = SubscriptionService(config)
        api.add_resource(SubscriptionResource, '/subscriptions', resource_class_args=[service])
