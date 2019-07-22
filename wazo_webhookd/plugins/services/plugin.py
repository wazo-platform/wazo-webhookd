# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from .http import ServicesResource


class Plugin:
    def load(self, dependencies):
        api = dependencies['api']
        services_manager = dependencies['service_manager']
        api.add_resource(
            ServicesResource,
            '/subscriptions/services',
            resource_class_args=[services_manager],
        )
