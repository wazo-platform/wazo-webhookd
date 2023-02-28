# Copyright 2017-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import signal
import threading

from functools import partial
from xivo import plugin_helpers
from xivo.consul_helpers import ServiceCatalogRegistration
from xivo.token_renewer import TokenRenewer
from wazo_auth_client import Client as AuthClient

from . import auth
from .bus import BusConsumer
from .rest_api import api, CoreRestApi
from wazo_webhookd import celery

logger = logging.getLogger(__name__)


class Controller:
    def __init__(self, config):
        self._stopping_thread = None
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
        self._token_renewer = TokenRenewer(self._auth_client)
        if not config['auth'].get('master_tenant_uuid'):
            self._token_renewer.subscribe_to_next_token_details_change(
                auth.init_master_tenant
            )
        self._token_renewer.subscribe_to_next_token_details_change(
            lambda t: self._token_renewer.emit_stop()
        )
        self._bus_consumer = BusConsumer(name='wazo_webhookd', **config['bus'])
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
                'next_token_change_subscribe': self._token_renewer.subscribe_to_next_token_change,
            },
        )

    def run(self):
        logger.info('wazo-webhookd starting...')
        signal.signal(signal.SIGTERM, partial(_signal_handler, self))
        signal.signal(signal.SIGINT, partial(_signal_handler, self))
        try:
            with ServiceCatalogRegistration(*self._service_discovery_args):
                with self._bus_consumer, self._token_renewer:
                    self.rest_api.run()
        finally:
            logger.info('wazo-webhookd stopping...')
            self._celery_process.terminate()
            logger.debug('waiting for remaining threads/subprocesses...')
            self._celery_process.join()
            if self._stopping_thread:
                self._stopping_thread.join()
            logger.debug('all threads and subprocesses stopped.')

    def stop(self, reason):
        logger.warning('Stopping wazo-webhookd: %s', reason)
        self._stopping_thread = threading.Thread(target=self.rest_api.stop, name=reason)
        self._stopping_thread.start()


def _signal_handler(controller, signum, frame):
    controller.stop(reason=signal.Signals(signum).name)
