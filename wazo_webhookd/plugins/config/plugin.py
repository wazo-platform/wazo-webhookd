# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from .resources import ConfigResource


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        config = dependencies['config']
        api.add_resource(ConfigResource, '/config', resource_class_args=[config])
