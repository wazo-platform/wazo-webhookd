# Copyright 2017-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that, calling, equal_to, has_entry, has_key, has_properties
from wazo_test_helpers import until
from wazo_test_helpers.hamcrest.raises import raises
from wazo_webhookd_client.exceptions import WebhookdError

from .helpers.base import MASTER_TOKEN, START_TIMEOUT, USER_1_TOKEN, BaseIntegrationTest
from .helpers.wait_strategy import EverythingOkWaitStrategy, WebhookdStartedWaitStrategy


class TestConfig(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = EverythingOkWaitStrategy()

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
        assert_that(
            calling(webhookd.config.patch).with_args(
                {'op': 'replace', 'path': '/debug', 'value': True}
            ),
            raises(WebhookdError, has_properties('status_code', 401)),
        )

    def test_restrict_when_service_token_not_initialized(self):
        def _returns_503(webhookd):
            assert_that(
                calling(webhookd.config.get),
                raises(WebhookdError).matching(
                    has_properties(
                        status_code=503,
                        error_id='master-tenant-not-initialized',
                    )
                ),
            )

        config = {'auth': {'username': 'invalid-service'}}
        with self.webhookd_with_config(config):
            webhookd = self.make_webhookd(MASTER_TOKEN)
            WebhookdStartedWaitStrategy().wait(webhookd)
            until.assert_(_returns_503, webhookd, timeout=START_TIMEOUT)
