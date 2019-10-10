# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import multiprocessing

from celery import Celery

app = Celery()

logger = logging.getLogger(__name__)


def configure(config):
    app.conf.accept_content = ['json']
    app.conf.broker_url = config['celery']['broker']
    app.conf.task_default_exchange = config['celery']['exchange_name']
    app.conf.task_default_queue = config['celery']['queue_name']
    app.conf.task_ignore_result = True
    app.conf.task_serializer = 'json'
    app.conf.worker_hijack_root_logger = False
    app.conf.worker_loglevel = logging.getLevelName(config['log_level']).upper()

    app.conf.worker_max_tasks_per_child = 1000
    app.conf.worker_max_memory_per_child = 100000


def spawn_workers(config):
    logger.debug('Starting Celery workers...')
    argv = [
        'webhookd-worker',  # argv[0] is arbitrary
        # NOTE(sileht): setproctitle must be installed to have the celery
        # process well named like:
        #   celeryd: webhookd@<hostname>:MainProcess
        #   celeryd: webhookd@<hostname>:Worker-*
        '--loglevel',
        logging.getLevelName(config['log_level']).upper(),
        '--hostname',
        'webhookd@%h',
        '--autoscale',
        "{},{}".format(config['celery']['worker_max'], config['celery']['worker_min']),
        '--pidfile',
        config['celery']['worker_pid_file'],
    ]
    process = multiprocessing.Process(target=app.worker_main, args=(argv,))
    process.start()
    return process


# NOTE(sileht): This defeat usage of stevedore but celery worker process need
# all tasks to be loaded when we create app Celery(). Also we don't want to
# load the whole plugin but just this task, we don't care about the rest
import wazo_webhookd.plugins.subscription.celery_tasks  # noqa
