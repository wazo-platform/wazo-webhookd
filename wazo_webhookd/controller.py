# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import signal

from functools import partial
from threading import Thread
from xivo import plugin_helpers
from xivo.consul_helpers import ServiceCatalogRegistration
from wazo_auth_client import Client as AuthClient

from .bus import CoreBusConsumer
from .rest_api import api, CoreRestApi
from wazo_webhookd import celery

logger = logging.getLogger(__name__)


class Controller:
    def __init__(self, config):
        # NOTE(sileht): Celery must be spawned before anything else, to ensure
        # we don't fork the process after some database/rabbitmq connection
        # have been established
        celery.configure(config)
        self._celery_process = celery.spawn_workers(config)

        self._service_discovery_args = [
            'wazo-webhookd',
            config.get('uuid'),
            config['consul'],
            config['service_discovery'],
            config['bus'],
            lambda: True,
        ]

        self._auth_client = AuthClient(**config['auth'])
        self._bus_consumer = CoreBusConsumer(config)
        self.rest_api = CoreRestApi(config)
        self._service_manager = plugin_helpers.load(
            namespace='wazo_webhookd.services',
            names=config['enabled_services'],
            dependencies={
                'api': api,
                'bus_consumer': self._bus_consumer,
                'config': config,
                'auth_client': self._auth_client,
            },
        )
        plugin_helpers.load(
            namespace='wazo_webhookd.plugins',
            names=config['enabled_plugins'],
            dependencies={
                'api': api,
                'bus_consumer': self._bus_consumer,
                'config': config,
                'service_manager': self._service_manager,
            },
        )

    def run(self):
        logger.info('wazo-webhookd starting...')
        signal.signal(signal.SIGTERM, partial(_sigterm_handler, self))
        bus_consumer_thread = Thread(
            target=self._bus_consumer.run, name='bus_consumer_thread'
        )
        bus_consumer_thread.start()
        try:
            with ServiceCatalogRegistration(*self._service_discovery_args):
                self.rest_api.run()
        finally:
            logger.info('wazo-webhookd stopping...')
            self._bus_consumer.should_stop = True
            self._celery_process.terminate()

            logger.debug('waiting for remaining threads/subprocesses...')
            bus_consumer_thread.join()
            self._celery_process.join()
            logger.debug('all threads and subprocesses stopped.')

    def stop(self, reason):
        logger.warning('Stopping wazo-webhookd: %s', reason)
        self.rest_api.stop()


def _sigterm_handler(controller, signum, frame):
    controller.stop(reason='SIGTERM')
