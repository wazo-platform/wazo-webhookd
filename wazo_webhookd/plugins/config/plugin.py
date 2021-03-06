# Copyright 2017-2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from .http import ConfigResource


class Plugin:
    def load(self, dependencies):
        api = dependencies['api']
        config = dependencies['config']
        api.add_resource(ConfigResource, '/config', resource_class_args=[config])
