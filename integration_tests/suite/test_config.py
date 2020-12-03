# Copyright 2017-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that, has_key, has_entry

from .helpers.base import BaseIntegrationTest
from .helpers.base import MASTER_TOKEN
from .helpers.wait_strategy import NoWaitStrategy


class TestConfig(BaseIntegrationTest):

    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def test_config(self):
        webhookd = self.make_webhookd(MASTER_TOKEN)

        result = webhookd.config.get()

        assert_that(result, has_key('rest_api'))

    def test_update_config(self):
        webhookd = self.make_webhookd(MASTER_TOKEN)

        debug_true_config = [
            {
                'op': 'replace',
                'path': '/debug',
                'value': True,
            }
        ]
        debug_false_config = [
            {
                'op': 'replace',
                'path': '/debug',
                'value': False,
            }
        ]

        webhookd.config.patch(debug_true_config)
        debug_true_config = webhookd.config.get()
        assert_that(debug_true_config, has_entry('debug', True))

        webhookd.config.patch(debug_false_config)
        debug_false_config = webhookd.config.get()
        assert_that(debug_false_config, has_entry('debug', False))
