# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from wazo_webhookd.celery import app


@app.task
def celery_task_sentinel() -> str:
    return 'sentinel'
