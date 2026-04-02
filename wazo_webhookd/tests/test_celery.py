# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from wazo_webhookd.celery import app, load_celery_tasks

EXPECTED_TASKS = [
    'wazo_webhookd.plugins.subscription.celery_tasks.hook_runner_task',
    'wazo_webhookd.plugins.mobile.celery_tasks.send_notification',
]


class TestLoadCeleryTasks:
    def test_loads_all_builtin_task_modules(self) -> None:
        config = {
            'enabled_celery_tasks': {
                'subscription': True,
                'mobile': True,
            },
        }

        load_celery_tasks(config)  # type: ignore[arg-type]

        registered = list(app.tasks.keys())
        for task_name in EXPECTED_TASKS:
            assert (
                task_name in registered
            ), f'{task_name} not found in registered tasks: {registered}'
