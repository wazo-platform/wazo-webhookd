# Copyright 2019-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import re

from hamcrest import assert_that, equal_to

from wazo_test_helpers import until

from .helpers.base import BaseIntegrationTest
from .helpers.wait_strategy import NoWaitStrategy


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
