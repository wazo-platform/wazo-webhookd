# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging
import time
import signal
import sys

from xivo.consul_helpers import ServiceCatalogRegistration

logger = logging.getLogger(__name__)


class Controller:

    def __init__(self, config):
        self.config = config
        self._service_discovery_args = [
            'wazo-webhookd',
            config.get('uuid'),
            config['consul'],
            config['service_discovery'],
            config['bus'],
            lambda: True,
        ]

    def run(self):
        signal.signal(signal.SIGTERM, _sigterm_handler)
        with ServiceCatalogRegistration(*self._service_discovery_args):
            while True:
                time.sleep(1)


def _sigterm_handler(signum, frame):
    logger.info('SIGTERM received, terminating')
    sys.exit(0)
