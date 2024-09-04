# Copyright 2017-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
import multiprocessing
from typing import TYPE_CHECKING

from celery import Celery

if TYPE_CHECKING:
    from wazo_webhookd.types import WebhookdConfigDict


app = Celery()
logger = logging.getLogger(__name__)


def configure(config: WebhookdConfigDict) -> None:
    app.conf.accept_content = ['json']
    app.conf.broker_url = config['celery']['broker']
    app.conf.task_default_exchange = config['celery']['exchange_name']
    app.conf.task_default_queue = config['celery']['queue_name']
    app.conf.task_ignore_result = True
    app.conf.task_serializer = 'json'
    app.conf.worker_hijack_root_logger = False
    app.conf.worker_loglevel = logging.getLevelName(config['log_level']).upper()

    app.conf.worker_max_tasks_per_child = 1_000
    app.conf.worker_max_memory_per_child = 100_000


def start_celery(argv: tuple[str, ...]) -> int | None:
    """
    This method implements the `worker_main` and `start` from Celery < 5.0
    Until we can update to Celery >= 5.0.3 where it was re-added.
    https://github.com/celery/celery/pull/6481/files
    """
    from celery.bin.celery import celery
    from click.exceptions import Exit

    celery.params[0].default = app

    try:
        celery.main(args=argv, standalone_mode=False)
    except Exit as e:
        return e.exit_code
    finally:
        celery.params[0].default = None
    return None


def spawn_workers(config: WebhookdConfigDict) -> multiprocessing.Process:
    logger.debug('Starting Celery workers...')
    argv = [
        'worker',
        # NOTE(sileht): setproctitle must be installed to have the celery
        # process well named like:
        #   celeryd: webhookd@<hostname>:MainProcess
        #   celeryd: webhookd@<hostname>:Worker-*
        '--loglevel',
        logging.getLevelName(config['log_level']).upper(),
        '--hostname',
        'webhookd@%h',
        '--autoscale',
        f"{config['celery']['worker_max']},{config['celery']['worker_min']}",
        '--pidfile',
        config['celery']['worker_pid_file'],
    ]
    process = multiprocessing.Process(target=start_celery, args=(argv,))
    process.start()
    return process


# NOTE(sileht): This defeats the point of using stevedore, but the celery worker process
# needs all tasks to be loaded when we create the Celery() app. Also, we don't want to
# load the whole plugin, just this task. We don't care about the rest.
import wazo_webhookd.plugins.mobile.celery_tasks  # noqa
import wazo_webhookd.plugins.subscription.celery_tasks  # noqa
