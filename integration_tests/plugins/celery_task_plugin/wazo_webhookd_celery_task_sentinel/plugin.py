# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from kombu.exceptions import OperationalError

logger = logging.getLogger(__name__)


def _dispatch_when_broker_ready() -> None:
    from .celery_tasks import celery_task_sentinel

    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            celery_task_sentinel.delay()
            return
        except OperationalError as exc:
            logger.debug('broker not ready, retrying: %r', exc)
            time.sleep(1)
    logger.error('gave up dispatching celery_task_sentinel: broker never reachable')


class Plugin:
    def load(self, dependencies: dict[str, Any]) -> None:
        threading.Thread(
            target=_dispatch_when_broker_ready,
            name='celery-task-sentinel-dispatch',
            daemon=True,
        ).start()
