# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from pathlib import Path

from wazo_webhookd.celery import app

MARKER_FILE = Path('/tmp/celery_task_sentinel_executed')


@app.task
def celery_task_sentinel() -> None:
    MARKER_FILE.write_text('ok')
