# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import Any


class Plugin:
    def load(self, dependencies: dict[str, Any]) -> None:
        from .celery_tasks import celery_task_sentinel

        celery_task_sentinel.apply_async(
            retry=True,
            retry_policy={
                'max_retries': 30,
                'interval_start': 0,
                'interval_step': 1.0,
                'interval_max': 2.0,
            },
        )
