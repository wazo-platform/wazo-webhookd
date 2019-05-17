# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that
from hamcrest import calling
from hamcrest import contains
from hamcrest import empty
from hamcrest import has_entries
from hamcrest import has_entry
from hamcrest import has_key
from hamcrest import has_item
from hamcrest import has_property
from hamcrest import not_
from wazo_webhookd_client.exceptions import WebhookdError
from xivo_test_helpers.auth import MockUserToken
from xivo_test_helpers.hamcrest.raises import raises

from .helpers.base import BaseIntegrationTest
from .helpers.base import VALID_TOKEN
from .helpers.fixtures import subscription
from .helpers.wait_strategy import NoWaitStrategy

SOME_SUBSCRIPTION_UUID = '07ec6a65-0f64-414a-bc8e-e2d1de0ae09d'
USER_1_UUID = '2eeb57e9-0506-4866-bce6-b626411fd133'
WAZO_UUID = 'cd030e68-ace9-4ad4-bc4e-13c8dec67898'

TEST_SUBSCRIPTION = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://test.example.com', 'method': 'get'},
    'events': ['test'],
}

TEST_SUBSCRIPTION_METADATA = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://test.example.com', 'method': 'get'},
    'events': ['test'],
    'metadata': {'key1': 'value1', 'key2': 'value2'},
}

ANOTHER_TEST_SUBSCRIPTION = {
    'name': 'test2',
    'service': 'http',
    'config': {'url': 'http://test2.example.com', 'method': 'post'},
    'events': ['test2'],
}

USER_1_TEST_SUBSCRIPTION = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://test.example.com', 'method': 'get'},
    'events': ['test'],
    'owner_user_uuid': USER_1_UUID,
    'events_user_uuid': USER_1_UUID,
    'events_wazo_uuid': WAZO_UUID,
}

UNOWNED_USER_1_TEST_SUBSCRIPTION = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://test.example.com', 'method': 'get'},
    'events': ['test'],
    'events_user_uuid': USER_1_UUID,
}

INVALID_SUBSCRIPTION = {}


class TestListSubscriptions(BaseIntegrationTest):

    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def test_given_wrong_auth_when_list_then_401(self):
        webhookd = self.make_webhookd('invalid-token')

        assert_that(
            calling(webhookd.subscriptions.list),
            raises(WebhookdError, has_property('status_code', 401)),
        )

    def test_given_no_subscriptions_when_list_then_empty(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        response = webhookd.subscriptions.list()

        assert_that(response, has_entries({'items': empty(), 'total': 0}))

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_subscription_when_list_then_list_one(self, subscription_):
        webhookd = self.make_webhookd(VALID_TOKEN)

        response = webhookd.subscriptions.list()

        assert_that(
            response,
            has_entries({'items': contains(has_entries(**subscription_)), 'total': 1}),
        )

    @subscription(TEST_SUBSCRIPTION)
    @subscription(TEST_SUBSCRIPTION_METADATA, track_test_name=False)
    def test_given_search_metadata_when_list_then_list_filtered(
        self, subscription_, subscription_metadata_
    ):
        webhookd = self.make_webhookd(VALID_TOKEN)

        response = webhookd.subscriptions.list(
            search_metadata=TEST_SUBSCRIPTION_METADATA['metadata']
        )

        assert_that(
            response,
            has_entries({'items': contains(has_entries(**TEST_SUBSCRIPTION_METADATA))}),
        )


class TestListUserSubscriptions(BaseIntegrationTest):

    asset = 'base'
    wait_strategy = NoWaitStrategy()

    @subscription(UNOWNED_USER_1_TEST_SUBSCRIPTION)
    @subscription(USER_1_TEST_SUBSCRIPTION)
    def test_given_subscriptions_when_user_list_then_list_only_subscriptions_of_this_user(
        self, _, user_subscription
    ):
        token = 'my-token'
        auth = self.make_auth()
        auth.set_token(MockUserToken(token, USER_1_UUID))
        webhookd = self.make_webhookd(token)

        response = webhookd.subscriptions.list_as_user()

        assert_that(
            response,
            has_entries(
                {'items': contains(has_entries(**user_subscription)), 'total': 1}
            ),
        )


class TestGetSubscriptions(BaseIntegrationTest):

    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def test_given_no_auth_server_when_get_subscription_then_503(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        with self.auth_stopped():
            assert_that(
                calling(webhookd.subscriptions.get).with_args(SOME_SUBSCRIPTION_UUID),
                raises(WebhookdError, has_property('status_code', 503)),
            )

    def test_given_wrong_auth_when_get_subscription_then_401(self):
        webhookd = self.make_webhookd('invalid-token')

        assert_that(
            calling(webhookd.subscriptions.get).with_args(SOME_SUBSCRIPTION_UUID),
            raises(WebhookdError, has_property('status_code', 401)),
        )

    def test_given_no_subscription_when_get_http_subscription_then_404(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        assert_that(
            calling(webhookd.subscriptions.get).with_args(SOME_SUBSCRIPTION_UUID),
            raises(WebhookdError, has_property('status_code', 404)),
        )

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_subscription_when_get_http_subscription_then_return_the_subscription(
        self, subscription_
    ):
        webhookd = self.make_webhookd(VALID_TOKEN)

        response = webhookd.subscriptions.get(subscription_['uuid'])

        assert_that(response, has_entries(subscription_))


class TestGetUserSubscriptions(BaseIntegrationTest):

    asset = 'base'
    wait_strategy = NoWaitStrategy()

    @subscription(UNOWNED_USER_1_TEST_SUBSCRIPTION)
    def test_given_non_user_subscription_when_user_get_http_subscription_then_404(
        self, subscription_
    ):
        token = 'my-token'
        auth = self.make_auth()
        auth.set_token(MockUserToken(token, USER_1_UUID))
        webhookd = self.make_webhookd(token)

        assert_that(
            calling(webhookd.subscriptions.get_as_user).with_args(
                subscription_['uuid']
            ),
            raises(WebhookdError, has_property('status_code', 404)),
        )

    @subscription(USER_1_TEST_SUBSCRIPTION)
    def test_given_user_subscription_when_user_get_http_subscription_then_return_the_subscription(
        self, subscription_
    ):
        token = 'my-token'
        auth = self.make_auth()
        auth.set_token(MockUserToken(token, USER_1_UUID))
        webhookd = self.make_webhookd(token)

        response = webhookd.subscriptions.get_as_user(subscription_['uuid'])

        assert_that(response, has_entries(subscription_))


class TestCreateSubscriptions(BaseIntegrationTest):

    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def test_given_no_auth_server_when_create_subscription_then_503(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        with self.auth_stopped():
            assert_that(
                calling(webhookd.subscriptions.create).with_args(TEST_SUBSCRIPTION),
                raises(WebhookdError, has_property('status_code', 503)),
            )

    def test_given_wrong_auth_when_create_subscription_then_401(self):
        webhookd = self.make_webhookd('invalid-token')

        assert_that(
            calling(webhookd.subscriptions.create).with_args(TEST_SUBSCRIPTION),
            raises(WebhookdError, has_property('status_code', 401)),
        )

    def test_when_create_invalid_subscription_then_400(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        assert_that(
            calling(webhookd.subscriptions.create).with_args(INVALID_SUBSCRIPTION),
            raises(WebhookdError, has_property('status_code', 400)),
        )

    def test_when_create_http_subscription_then_subscription_no_error(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        response = webhookd.subscriptions.create(TEST_SUBSCRIPTION)
        subscription_uuid = response['uuid']

        assert_that(response, has_key('uuid'))

        response = webhookd.subscriptions.list()
        assert_that(
            response, has_entry('items', has_item(has_entry('uuid', subscription_uuid)))
        )

    def given_metadata_when_create_subscription_then_metadata_are_attached(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        response = webhookd.subscriptions.create(TEST_SUBSCRIPTION_METADATA)
        subscription_uuid = response['uuid']

        assert_that(response, has_key('uuid'))

        response = webhookd.subscriptions.get(subscription_uuid)
        assert_that(
            response, has_entry('metadata', TEST_SUBSCRIPTION_METADATA['metadata'])
        )


class TestCreateUserSubscriptions(BaseIntegrationTest):

    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def test_when_create_http_user_subscription_then_subscription_no_error(self):
        token = 'my-token'
        user_uuid = '575630df-5334-4e99-86d7-56596d77228d'
        wazo_uuid = '50265257-9dcf-4e9d-b6ce-3a1c0ae3b733'
        auth = self.make_auth()
        auth.set_token(MockUserToken(token, user_uuid, wazo_uuid))
        webhookd = self.make_webhookd(token)

        response = webhookd.subscriptions.create_as_user(TEST_SUBSCRIPTION)

        assert_that(
            response,
            has_entries(
                {
                    'events_user_uuid': user_uuid,
                    'events_wazo_uuid': wazo_uuid,
                    'owner_user_uuid': user_uuid,
                }
            ),
        )

    def test_given_events_user_uuid_when_create_http_user_subscription_then_events_user_uuid_ignored(
        self
    ):
        token = 'my-token'
        user_uuid = '575630df-5334-4e99-86d7-56596d77228d'
        wazo_uuid = '50265257-9dcf-4e9d-b6ce-3a1c0ae3b733'
        auth = self.make_auth()
        auth.set_token(MockUserToken(token, user_uuid, wazo_uuid))
        webhookd = self.make_webhookd(token)

        response = webhookd.subscriptions.create_as_user(USER_1_TEST_SUBSCRIPTION)

        assert_that(
            response,
            has_entries(
                {
                    'events_user_uuid': user_uuid,
                    'events_wazo_uuid': wazo_uuid,
                    'owner_user_uuid': user_uuid,
                }
            ),
        )


class TestEditSubscriptions(BaseIntegrationTest):

    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def test_given_no_auth_server_when_edit_subscription_then_503(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        with self.auth_stopped():
            assert_that(
                calling(webhookd.subscriptions.update).with_args(
                    SOME_SUBSCRIPTION_UUID, ANOTHER_TEST_SUBSCRIPTION
                ),
                raises(WebhookdError, has_property('status_code', 503)),
            )

    def test_given_wrong_auth_when_edit_subscription_then_401(self):
        webhookd = self.make_webhookd('invalid-token')

        assert_that(
            calling(webhookd.subscriptions.update).with_args(
                SOME_SUBSCRIPTION_UUID, ANOTHER_TEST_SUBSCRIPTION
            ),
            raises(WebhookdError, has_property('status_code', 401)),
        )

    def test_given_no_subscription_when_edit_http_subscription_then_404(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        assert_that(
            calling(webhookd.subscriptions.update).with_args(
                SOME_SUBSCRIPTION_UUID, ANOTHER_TEST_SUBSCRIPTION
            ),
            raises(WebhookdError, has_property('status_code', 404)),
        )

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_subscription_when_edit_invalid_http_subscription_then_400(
        self, subscription_
    ):
        webhookd = self.make_webhookd(VALID_TOKEN)

        assert_that(
            calling(webhookd.subscriptions.update).with_args(
                SOME_SUBSCRIPTION_UUID, INVALID_SUBSCRIPTION
            ),
            raises(WebhookdError, has_property('status_code', 400)),
        )

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_subscription_when_edit_http_subscription_then_edited(
        self, subscription_
    ):
        webhookd = self.make_webhookd(VALID_TOKEN)
        expected_subscription = dict(
            uuid=subscription_['uuid'], **ANOTHER_TEST_SUBSCRIPTION
        )

        webhookd.subscriptions.update(subscription_['uuid'], ANOTHER_TEST_SUBSCRIPTION)

        response = webhookd.subscriptions.get(subscription_['uuid'])
        assert_that(response, has_entries(expected_subscription))

        response = webhookd.subscriptions.list()
        assert_that(
            response, has_entry('items', has_item(has_entries(expected_subscription)))
        )

    @subscription(TEST_SUBSCRIPTION_METADATA)
    def given_metadata_when_edit_subscription_then_metadata_are_replaced(
        self, subscription_
    ):
        webhookd = self.make_webhookd(VALID_TOKEN)
        subscription_uuid = subscription_['uuid']

        subscription_['metadata'] = {'new_key': 'new_value', 'another_new_key': 'value'}

        webhookd.subscriptions.update(subscription_uuid, subscription_)

        response = webhookd.subscriptions.get(subscription_['uuid'])
        assert_that(response, has_entry('metadata', subscription_['metadata']))


class TestEditUserSubscriptions(BaseIntegrationTest):

    asset = 'base'
    wait_strategy = NoWaitStrategy()

    @subscription(UNOWNED_USER_1_TEST_SUBSCRIPTION)
    def test_given_non_user_subscription_when_user_edit_http_subscription_then_404(
        self, subscription_
    ):
        token = 'my-token'
        auth = self.make_auth()
        auth.set_token(MockUserToken(token, USER_1_UUID))
        webhookd = self.make_webhookd(token)

        assert_that(
            calling(webhookd.subscriptions.update_as_user).with_args(
                subscription_['uuid'], ANOTHER_TEST_SUBSCRIPTION
            ),
            raises(WebhookdError, has_property('status_code', 404)),
        )

    @subscription(USER_1_TEST_SUBSCRIPTION)
    def test_given_user_subscription_when_user_edit_http_subscription_then_updated(
        self, subscription_
    ):
        token = 'my-token'
        auth = self.make_auth()
        auth.set_token(MockUserToken(token, USER_1_UUID))
        webhookd = self.make_webhookd(token)
        new_subscription = dict(subscription_)
        new_subscription['uuid'] = 'should-be-ignored'
        new_subscription['events_user_uuid'] = 'should-be-ignored'
        new_subscription['name'] = 'new-name'

        webhookd.subscriptions.update_as_user(subscription_['uuid'], new_subscription)

        response = webhookd.subscriptions.list_as_user()
        assert_that(
            response,
            has_entry(
                'items',
                has_item(
                    has_entries(
                        {
                            'uuid': subscription_['uuid'],
                            'events_user_uuid': subscription_['events_user_uuid'],
                            'name': 'new-name',
                        }
                    )
                ),
            ),
        )


class TestDeleteSubscriptions(BaseIntegrationTest):

    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def test_given_no_auth_server_when_delete_subscription_then_503(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        with self.auth_stopped():
            assert_that(
                calling(webhookd.subscriptions.delete).with_args(
                    SOME_SUBSCRIPTION_UUID
                ),
                raises(WebhookdError, has_property('status_code', 503)),
            )

    def test_given_wrong_auth_when_delete_subscription_then_401(self):
        webhookd = self.make_webhookd('invalid-token')

        assert_that(
            calling(webhookd.subscriptions.delete).with_args(SOME_SUBSCRIPTION_UUID),
            raises(WebhookdError, has_property('status_code', 401)),
        )

    def test_given_no_subscription_when_delete_http_subscription_then_404(self):
        webhookd = self.make_webhookd(VALID_TOKEN)

        assert_that(
            calling(webhookd.subscriptions.delete).with_args(SOME_SUBSCRIPTION_UUID),
            raises(WebhookdError, has_property('status_code', 404)),
        )

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_subscription_when_delete_http_subscription_then_deleted(
        self, subscription_
    ):
        webhookd = self.make_webhookd(VALID_TOKEN)

        webhookd.subscriptions.delete(subscription_['uuid'])

        response = webhookd.subscriptions.list()
        assert_that(
            response,
            has_entry(
                'items', not_(has_item(has_entry('uuid', subscription_['uuid'])))
            ),
        )


class TestDeleteUserSubscriptions(BaseIntegrationTest):

    asset = 'base'
    wait_strategy = NoWaitStrategy()

    @subscription(UNOWNED_USER_1_TEST_SUBSCRIPTION)
    def test_given_non_user_subscription_when_user_delete_http_subscription_then_404(
        self, subscription_
    ):
        token = 'my-token'
        auth = self.make_auth()
        auth.set_token(MockUserToken(token, USER_1_UUID))
        webhookd = self.make_webhookd(token)

        assert_that(
            calling(webhookd.subscriptions.delete_as_user).with_args(
                subscription_['uuid']
            ),
            raises(WebhookdError, has_property('status_code', 404)),
        )

    @subscription(USER_1_TEST_SUBSCRIPTION)
    def test_given_user_subscription_when_user_delete_http_subscription_then_deleted(
        self, subscription_
    ):
        token = 'my-token'
        auth = self.make_auth()
        auth.set_token(MockUserToken(token, USER_1_UUID))
        webhookd = self.make_webhookd(token)

        webhookd.subscriptions.delete_as_user(subscription_['uuid'])

        response = webhookd.subscriptions.list_as_user()
        assert_that(
            response,
            has_entry(
                'items', not_(has_item(has_entry('uuid', subscription_['uuid'])))
            ),
        )
