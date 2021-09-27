# Copyright 2017-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from time import sleep
from requests import RequestException
from hamcrest import assert_that, equal_to, has_key, has_entry, has_properties, calling
from xivo_test_helpers import until
from xivo_test_helpers.hamcrest.raises import raises

from wazo_webhookd_client.exceptions import WebhookdError

from .helpers.base import BaseIntegrationTest
from .helpers.base import MASTER_TOKEN, USER_1_TOKEN
from .helpers.wait_strategy import NoWaitStrategy


class TestConfig(BaseIntegrationTest):

    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def test_config(self):
        sleep(5)  # Necessary wait for services to initialize
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

        debug_true_patched_config = webhookd.config.patch(debug_true_config)
        debug_true_config = webhookd.config.get()
        assert_that(debug_true_config, has_entry('debug', True))
        assert_that(debug_true_patched_config, equal_to(debug_true_config))

        debug_false_patched_config = webhookd.config.patch(debug_false_config)
        debug_false_config = webhookd.config.get()
        assert_that(debug_false_config, has_entry('debug', False))
        assert_that(debug_false_patched_config, equal_to(debug_false_config))

    def test_restrict_only_master_tenant(self):
        webhookd = self.make_webhookd(USER_1_TOKEN)
        assert_that(
            calling(webhookd.config.get),
            raises(WebhookdError, has_properties('status_code', 401)),
        )

    def test_restrict_on_with_slow_wazo_auth(self):
        self.stop_service('webhookd')
        self.stop_service('auth')
        self.start_service('webhookd')

        webhookd = self.make_webhookd(MASTER_TOKEN)

        def _returns_503():
            try:
                webhookd.config.get()
            except WebhookdError as e:
                assert e.status_code == 503
            except RequestException as e:
                raise AssertionError(e)
            else:
                raise AssertionError('Should not return a success')

        until.assert_(_returns_503, tries=10)

        self.start_service('auth')
        self.configured_wazo_auth()

        def _not_return_503():
            try:
                response = webhookd.config.get()
                assert_that(response, has_key('debug'))
            except Exception as e:
                raise AssertionError(e)

        until.assert_(_not_return_503, tries=10)
