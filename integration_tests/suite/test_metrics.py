# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import requests
from hamcrest import assert_that, contains_string, equal_to

from .helpers.base import MASTER_TOKEN, BaseIntegrationTest
from .helpers.wait_strategy import WebhookdStartedWaitStrategy


class TestMetrics(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = WebhookdStartedWaitStrategy()

    def _url(self, path):
        return f'http://127.0.0.1:{self.service_port(9300, "webhookd")}/1.0/{path}'

    def test_metrics_without_token(self):
        self.make_webhookd(MASTER_TOKEN).status.get()

        response = requests.get(self._url('metrics'))

        assert_that(response.status_code, equal_to(200))
        assert_that(
            response.text,
            contains_string('flask_http_request_total{method="GET",status="200"}'),
        )
        assert_that(
            response.text,
            contains_string(
                'flask_http_request_duration_seconds_count'
                '{endpoint="statusresource",method="GET",status="200"}'
            ),
        )
