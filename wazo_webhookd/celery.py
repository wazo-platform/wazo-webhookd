# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from celery import Celery

app = Celery()

logger = logging.getLogger(__name__)


class CoreCeleryWorker():

    def __init__(self, config):
        app.conf.update(
            CELERYD_LOG_LEVEL=logging.getLevelName(config['log_level']),
            CELERY_TASK_SERIALIZER='json',
            CELERY_ACCEPT_CONTENT=['json'],
            BROKER_URL=config['celery']['broker'],
            CELERY_DEFAULT_EXCHANGE=config['celery']['exchange_name'],
            CELERY_DEFAULT_QUEUE=config['celery']['queue_name'],
            CELERYD_HIJACK_ROOT_LOGGER=False,
            CELERY_IGNORE_RESULT=True,
            CELERY_WORKER_MIN=config['celery']['worker_min'],
            CELERY_WORKER_MAX=config['celery']['worker_max'],
        )
        self._worker_pid_file = config['celery']['worker_pid_file']

    def run(self):
        logger.debug('Starting Celery worker...')
        argv = [
            'webhookd-worker',  # argv[0] is arbitrary
            '--loglevel', app.conf['CELERYD_LOG_LEVEL'].upper(),
            # NOTE(sileht): setproctitle must be installed to have the celery
            # process well named like:
            #   celeryd: webhookd@<hostname>:MainProcess
            #   celeryd: webhookd@<hostname>:Worker-*
            '--hostname', 'webhookd@%h',
            '--autoscale', "{},{}".format(
                app.conf['CELERY_WORKER_MAX'],
                app.conf['CELERY_WORKER_MIN']
            ),
            '--pidfile', self._worker_pid_file,
        ]
        return app.worker_main(argv)
