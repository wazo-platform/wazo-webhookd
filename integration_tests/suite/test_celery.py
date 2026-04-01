# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import re
import textwrap

from hamcrest import assert_that, equal_to, has_item
from wazo_test_helpers import until

from .helpers.base import BaseIntegrationTest
from .helpers.wait_strategy import NoWaitStrategy

SENTINEL_TASK = 'wazo_webhookd_celery_task_sentinel.celery_tasks.celery_task_sentinel'


class TestCeleryWorks(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def test_we_have_3_workers_by_default(self):
        def check_ps():
            output = self.docker_exec(["ps", "-eo", "cmd"]).decode()

            master_found = False
            worker_count = 0
            for line in output.split("\n"):
                if re.match(r"\[celeryd: webhookd@.*:MainProcess\] .*", line):
                    master_found = True
                elif re.match(r"\[celeryd: webhookd@.*:ForkPoolWorker-.\]", line):
                    worker_count += 1

            assert_that(master_found, equal_to(True))
            assert_that(worker_count, equal_to(3), output)

        until.assert_(check_ps, timeout=10, interval=0.5)

    def test_external_celery_task_plugin_is_registered(self) -> None:
        def check_task_registered() -> None:
            output = self.docker_exec(
                [
                    'python3',
                    '-c',
                    textwrap.dedent(
                        """
                    from wazo_webhookd.celery import app, load_celery_tasks;
                    load_celery_tasks({
                      "enabled_celery_tasks": {"celery_task_sentinel": True}
                    });
                    print("\\n".join(app.tasks.keys()))
                    """
                    ),
                ]
            ).decode()
            tasks = output.strip().split('\n')
            assert_that(tasks, has_item(SENTINEL_TASK))

        until.assert_(check_task_registered, timeout=10, interval=0.5)
