# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from .resources import SubscriptionsResource
from .service import SubscriptionsService


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        config = dependencies['config']
        service = SubscriptionsService(config)
        api.add_resource(SubscriptionsResource, '/subscriptions', resource_class_args=[service])
