# Copyright 2017-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from .http import StatusResource


class Plugin:
    def load(self, dependencies):
        api = dependencies['api']
        bus_consumer = dependencies['bus_consumer']
        config = dependencies['config']

        api.add_resource(
            StatusResource, '/status', resource_class_args=[bus_consumer, config]
        )
