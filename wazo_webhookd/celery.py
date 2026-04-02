# Copyright 2017-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
import multiprocessing
from functools import partial
from typing import TYPE_CHECKING

from celery import Celery
from stevedore.named import NamedExtensionManager
from xivo.plugin_helpers import enabled_names, on_load_failure, on_missing_entrypoints

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


CELERY_TASKS_NAMESPACE = 'wazo_webhookd.celery_tasks'


def load_celery_tasks(config: WebhookdConfigDict) -> None:
    """Load celery task modules via stevedore entry points.

    Must be called after configure() and before spawn_workers(),
    so that all @app.task-decorated functions are registered
    before the worker process is forked.

    Entry points reference modules (not classes). Importing the module
    is sufficient to register tasks via @app.task decorators.
    """
    names = enabled_names(config['enabled_celery_tasks'])
    if not names:
        logger.info('No celery task modules enabled')
        return

    NamedExtensionManager(
        CELERY_TASKS_NAMESPACE,
        names,
        on_load_failure_callback=on_load_failure,
        on_missing_entrypoints_callback=partial(
            on_missing_entrypoints, CELERY_TASKS_NAMESPACE
        ),
        invoke_on_load=False,
    )
