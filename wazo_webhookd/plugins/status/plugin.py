# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from .resource import StatusResource


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        bus_consumer = dependencies['bus_consumer']

        api.add_resource(StatusResource, '/status', resource_class_args=[bus_consumer])
