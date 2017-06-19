# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import requests

from hamcrest import assert_that
from hamcrest import has_key

from .test_api.base import BaseIntegrationTest
from .test_api.base import VALID_TOKEN


class TestDocumentation(BaseIntegrationTest):

    asset = 'base'

    def test_config(self):
        config_url = 'https://localhost:{port}/1.0/config'.format(port=self.service_port(9300, 'webhookd'))

        result = requests.get(config_url, headers={'X-Auth-Token': VALID_TOKEN}, verify=False).json()

        assert_that(result, has_key('rest_api'))
