# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import assert_that
from hamcrest import has_key

from .test_api.base import BaseIntegrationTest
from .test_api.base import VALID_TOKEN


class TestConfig(BaseIntegrationTest):

    asset = 'base'

    def test_config(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        result = webhookd.config.get()

        assert_that(result, has_key('rest_api'))
