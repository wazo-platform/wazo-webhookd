# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging
import signal

from functools import partial
from xivo.consul_helpers import ServiceCatalogRegistration
from wazo_webhookd.core import plugin_manager
from wazo_webhookd.core.rest_api import api, CoreRestApi

logger = logging.getLogger(__name__)


class Controller:

    def __init__(self, config):
        self._service_discovery_args = [
            'wazo-webhookd',
            config.get('uuid'),
            config['consul'],
            config['service_discovery'],
            config['bus'],
            lambda: True,
        ]
        self.rest_api = CoreRestApi(config)
        self._load_plugins(config)

    def run(self):
        signal.signal(signal.SIGTERM, partial(_sigterm_handler, self))
        with ServiceCatalogRegistration(*self._service_discovery_args):
            self.rest_api.run()

    def stop(self, reason):
        logger.warning('Stopping wazo-webhookd: %s', reason)
        self.rest_api.stop()

    def _load_plugins(self, global_config):
        load_args = [{
            'api': api,
            'config': global_config,
        }]
        plugin_manager.load_plugins(global_config['enabled_plugins'], load_args)


def _sigterm_handler(controller, signum, frame):
    controller.stop(reason='SIGTERM')
