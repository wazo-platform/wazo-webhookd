# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging
import signal

from functools import partial
from multiprocessing import Process
from threading import Thread
from xivo.consul_helpers import ServiceCatalogRegistration
from wazo_webhookd.core import plugin_manager
from wazo_webhookd.core import service_manager
from wazo_webhookd.core.bus import CoreBusConsumer
from wazo_webhookd.core.celery import CoreCeleryWorker
from wazo_webhookd.core.celery import app as celery_app
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
        self._bus_consumer = CoreBusConsumer(config)
        self._celery_worker = CoreCeleryWorker(config)
        self.rest_api = CoreRestApi(config)
        service_load_args = [{
            'api': api,
        }]
        self._service_manager = service_manager.load_services(config['enabled_services'], service_load_args)
        self._load_plugins(config)

    def run(self):
        logger.info('wazo-webhookd starting...')
        signal.signal(signal.SIGTERM, partial(_sigterm_handler, self))
        celery_process = Process(target=self._celery_worker.run, name='celery_process')
        celery_process.start()
        bus_consumer_thread = Thread(target=self._bus_consumer.run, name='bus_consumer_thread')
        bus_consumer_thread.start()
        try:
            with ServiceCatalogRegistration(*self._service_discovery_args):
                self.rest_api.run()
        finally:
            logger.info('wazo-webhookd stopping...')
            self._bus_consumer.should_stop = True
            logger.debug('waiting for remaining threads...')
            bus_consumer_thread.join()
            logger.debug('all threads stopped.')

    def stop(self, reason):
        logger.warning('Stopping wazo-webhookd: %s', reason)
        self.rest_api.stop()

    def _load_plugins(self, global_config):
        load_args = [{
            'api': api,
            'bus_consumer': self._bus_consumer,
            'celery': celery_app,
            'config': global_config,
            'service_manager': self._service_manager,
        }]
        plugin_manager.load_plugins(global_config['enabled_plugins'], load_args)


def _sigterm_handler(controller, signum, frame):
    controller.stop(reason='SIGTERM')
