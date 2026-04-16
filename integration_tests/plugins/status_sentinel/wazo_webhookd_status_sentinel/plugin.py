# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo.status import Status


def _provide_test_status(status):
    status['test_component']['status'] = Status.ok


class Plugin:
    def load(self, dependencies):
        status_aggregator = dependencies['status_aggregator']
        status_aggregator.add_provider(_provide_test_status)
