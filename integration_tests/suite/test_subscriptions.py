# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import assert_that
from hamcrest import calling
from hamcrest import contains
from hamcrest import empty
from hamcrest import equal_to
from hamcrest import has_entries
from hamcrest import has_entry
from hamcrest import has_key
from hamcrest import has_item
from hamcrest import has_property
from hamcrest import not_
from wazo_webhookd_client.exceptions import WebhookdError
from xivo_test_helpers.hamcrest.raises import raises

from .test_api.base import BaseIntegrationTest
from .test_api.base import VALID_TOKEN
from .test_api.fixtures import subscription

SOME_SUBSCRIPTION_UUID = '07ec6a65-0f64-414a-bc8e-e2d1de0ae09d'

TEST_SUBSCRIPTION = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://test.example.com',
               'method': 'get'},
    'events': ['test']
}

ANOTHER_TEST_SUBSCRIPTION = {
    'name': 'test2',
    'service': 'http',
    'config': {'url': 'http://test2.example.com',
               'method': 'post'},
    'events': ['test2']
}


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

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_subscription_when_list_then_list_one(self, subscription_):
        webhookd = self.make_webhookd(VALID_TOKEN)

        response = webhookd.subscriptions.list()

        assert_that(response, has_entries({
            'items': contains(has_entries(**subscription_)),
            'total': 1
        }))


class TestGetSubscriptions(BaseIntegrationTest):

    asset = 'base'

    def test_given_no_auth_server_when_get_subscription_then_503(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        with self.auth_stopped():
            assert_that(calling(webhookd.subscriptions.get).with_args(SOME_SUBSCRIPTION_UUID),
                        raises(WebhookdError, has_property('status_code', 503)))

    def test_given_wrong_auth_when_get_subscription_then_401(self):
        webhookd = self.make_webhookd('invalid-token')

        assert_that(calling(webhookd.subscriptions.get).with_args(SOME_SUBSCRIPTION_UUID),
                    raises(WebhookdError, has_property('status_code', 401)))

    def test_given_no_subscription_when_get_http_subscription_then_404(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        assert_that(calling(webhookd.subscriptions.get).with_args(SOME_SUBSCRIPTION_UUID),
                    raises(WebhookdError, has_property('status_code', 404)))

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_subscription_when_get_http_subscription_then_return_the_subscription(self, subscription_):
        webhookd = self.make_webhookd(VALID_TOKEN)

        response = webhookd.subscriptions.get(subscription_['uuid'])

        assert_that(response, equal_to(subscription_))


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

        subscription = TEST_SUBSCRIPTION
        response = webhookd.subscriptions.create(subscription)
        subscription_uuid = response['uuid']

        assert_that(response, has_key('uuid'))

        response = webhookd.subscriptions.list()
        assert_that(response, has_entry('items', has_item(has_entry('uuid', subscription_uuid))))


class TestEditSubscriptions(BaseIntegrationTest):

    asset = 'base'

    def test_given_no_auth_server_when_edit_subscription_then_503(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        with self.auth_stopped():
            assert_that(calling(webhookd.subscriptions.edit).with_args(SOME_SUBSCRIPTION_UUID, ANOTHER_TEST_SUBSCRIPTION),
                        raises(WebhookdError, has_property('status_code', 503)))

    def test_given_wrong_auth_when_edit_subscription_then_401(self):
        webhookd = self.make_webhookd('invalid-token')

        assert_that(calling(webhookd.subscriptions.edit).with_args(SOME_SUBSCRIPTION_UUID, ANOTHER_TEST_SUBSCRIPTION),
                    raises(WebhookdError, has_property('status_code', 401)))

    def test_given_no_subscription_when_edit_http_subscription_then_404(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        assert_that(calling(webhookd.subscriptions.edit).with_args(SOME_SUBSCRIPTION_UUID, ANOTHER_TEST_SUBSCRIPTION),
                    raises(WebhookdError, has_property('status_code', 404)))

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_subscription_when_edit_http_subscription_then_edited(self, subscription_):
        webhookd = self.make_webhookd(VALID_TOKEN)
        expected_subscription = dict(uuid=subscription_['uuid'], **ANOTHER_TEST_SUBSCRIPTION)

        webhookd.subscriptions.edit(subscription_['uuid'], ANOTHER_TEST_SUBSCRIPTION)

        response = webhookd.subscriptions.get(subscription_['uuid'])
        assert_that(response, has_entries(expected_subscription))

        response = webhookd.subscriptions.list()
        assert_that(response, has_entry('items', has_item(has_entries(expected_subscription))))


class TestDeleteSubscriptions(BaseIntegrationTest):

    asset = 'base'

    def test_given_no_auth_server_when_delete_subscription_then_503(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        with self.auth_stopped():
            assert_that(calling(webhookd.subscriptions.delete).with_args(SOME_SUBSCRIPTION_UUID),
                        raises(WebhookdError, has_property('status_code', 503)))

    def test_given_wrong_auth_when_delete_subscription_then_401(self):
        webhookd = self.make_webhookd('invalid-token')

        assert_that(calling(webhookd.subscriptions.delete).with_args(SOME_SUBSCRIPTION_UUID),
                    raises(WebhookdError, has_property('status_code', 401)))

    def test_given_no_subscription_when_delete_http_subscription_then_404(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        assert_that(calling(webhookd.subscriptions.delete).with_args(SOME_SUBSCRIPTION_UUID),
                    raises(WebhookdError, has_property('status_code', 404)))

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_subscription_when_delete_http_subscription_then_deleted(self, subscription_):
        webhookd = self.make_webhookd(VALID_TOKEN)

        webhookd.subscriptions.delete(subscription_['uuid'])

        response = webhookd.subscriptions.list()
        assert_that(response, has_entry('items', not_(has_item(has_entry('uuid', subscription_['uuid'])))))
