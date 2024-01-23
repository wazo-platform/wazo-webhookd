# Copyright 2017-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that, has_entry, has_key

from .helpers.base import MASTER_TOKEN, BaseIntegrationTest
from .helpers.wait_strategy import NoWaitStrategy


class TestConfig(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def test_config(self):
        webhookd = self.make_webhookd(MASTER_TOKEN)

        result = webhookd.subscriptions.list_services()

        assert_that(result, has_entry('services', has_key('http')))
