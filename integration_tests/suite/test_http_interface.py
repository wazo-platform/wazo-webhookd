# Copyright 2017-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import requests

from .helpers.base import MASTER_TOKEN, BaseIntegrationTest
from .helpers.wait_strategy import EverythingOkWaitStrategy


class TestHTTPInterface(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = EverythingOkWaitStrategy()

    def test_that_empty_body_returns_400(self):
        port = self.service_port(9300, 'webhookd')
        url = f'http://127.0.0.1:{port}/1.0/config'
        headers = {'X-Auth-Token': MASTER_TOKEN}

        response = requests.patch(url, data='', headers=headers)
        assert response.status_code == 400

        response = requests.patch(url, json=None, headers=headers)
        assert response.status_code == 400
