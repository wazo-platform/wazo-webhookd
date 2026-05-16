# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from pathlib import Path

from celery.utils.log import get_task_logger

from wazo_webhookd.celery import app

MARKER_FILE = Path('/tmp/celery_task_sentinel_executed')

logger = get_task_logger(__name__)


@app.task
def celery_task_sentinel() -> None:
    try:
        MARKER_FILE.write_text('ok')
    except Exception as e:
        logger.error("Error while writing sentinel file: %r", e, exc_info=True)
