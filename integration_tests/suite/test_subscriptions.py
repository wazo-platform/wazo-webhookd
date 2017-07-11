# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import assert_that
from hamcrest import calling
from hamcrest import empty
from hamcrest import has_entries
from hamcrest import has_key
from hamcrest import has_property
from wazo_webhookd_client.exceptions import WebhookdError
from xivo_test_helpers.hamcrest.raises import raises

from .test_api.base import BaseIntegrationTest
from .test_api.base import VALID_TOKEN


class TestListSubscriptions(BaseIntegrationTest):

    asset = 'base'

    def test_given_wrong_auth_when_list_then_401(self):
        webhookd = self.make_webhookd('invalid-token')

        assert_that(calling(webhookd.subscriptions.list),
                    raises(WebhookdError, has_property('status_code', 401)))

    def test_given_no_subscriptions_when_list_then_empty(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        response = webhookd.subscriptions.list()

        assert_that(response, has_entries({'items': empty(),
                                           'total': 0}))


class TestCreateSubscriptions(BaseIntegrationTest):

    asset = 'base'

    def test_given_no_auth_server_when_create_subscription_then_503(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        with self.auth_stopped():
            assert_that(calling(webhookd.subscriptions.create).with_args({}),
                        raises(WebhookdError, has_property('status_code', 503)))

    def test_given_wrong_auth_when_create_subscription_then_401(self):
        webhookd = self.make_webhookd('invalid-token')

        assert_that(calling(webhookd.subscriptions.create).with_args({}),
                    raises(WebhookdError, has_property('status_code', 401)))

    def test_when_create_http_subscription_then_subscription_no_error(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        subscription = {'name': 'test',
                        'service': 'http',
                        'config': {'url': 'http://test.example.com',
                                   'method': 'get'},
                        'events': []}
        response = webhookd.subscriptions.create(subscription)

        assert_that(response, has_key('uuid'))
