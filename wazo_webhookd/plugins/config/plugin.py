# Copyright 2017-2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from .http import ConfigResource
from .http import ConfigDebugResource
from .service import ConfigService


class Plugin:
    def load(self, dependencies):
        api = dependencies['api']
        config = dependencies['config']
        config_service = ConfigService(config)
        api.add_resource(ConfigResource, '/config', resource_class_args=[config])
        api.add_resource(
            ConfigDebugResource, '/config/debug', resource_class_args=[config_service]
        )
