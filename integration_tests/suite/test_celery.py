# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import re

from hamcrest import assert_that, equal_to
from wazo_test_helpers import until

from .helpers.base import BaseIntegrationTest
from .helpers.wait_strategy import NoWaitStrategy, TestComponentConnectedWaitStrategy

MARKER_FILE = '/tmp/celery_task_sentinel_executed'


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


class TestCeleryTaskPlugin(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = TestComponentConnectedWaitStrategy()

    def tearDown(self) -> None:
        self.docker_exec(['rm', '-f', MARKER_FILE])
        super().tearDown()

    def test_external_celery_task_is_executed(self) -> None:
        # celery_task_sentinel plugin dispatches a task on load(),
        # which writes a marker file when the celery worker executes it
        def check_marker_exists() -> None:
            output = self.docker_exec(['cat', MARKER_FILE]).decode().strip()
            assert_that(output, equal_to('ok'))

        until.assert_(check_marker_exists, timeout=15, interval=0.5)
