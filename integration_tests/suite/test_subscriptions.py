# Copyright 2017-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Any

from hamcrest import (
    assert_that,
    calling,
    contains_exactly,
    contains_inanyorder,
    empty,
    equal_to,
    has_entries,
    has_entry,
    has_item,
    has_key,
    has_length,
    has_property,
    instance_of,
    not_,
)
from wazo_test_helpers import until
from wazo_test_helpers.hamcrest.raises import raises
from wazo_webhookd_client.exceptions import WebhookdError

from .helpers.base import (
    MASTER_TENANT,
    MASTER_TOKEN,
    OTHER_TENANT,
    OTHER_USER_TOKEN,
    OTHER_USER_UUID,
    SOME_ROUTING_KEY,
    USER_1_TOKEN,
    USER_1_UUID,
    USER_2_TOKEN,
    USER_2_UUID,
    USERS_TENANT,
    WAZO_UUID,
    BaseIntegrationTest,
)
from .helpers.fixtures import SubscriptionFixtureMixin, subscription, user_subscription
from .helpers.wait_strategy import EverythingOkWaitStrategy

SOME_SUBSCRIPTION_UUID = '07ec6a65-0f64-414a-bc8e-e2d1de0ae09d'

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

USER_2_TEST_SUBSCRIPTION = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://test.example.com', 'method': 'get'},
    'events': ['test'],
    'owner_user_uuid': USER_2_UUID,
    'events_user_uuid': USER_2_UUID,
    'events_wazo_uuid': WAZO_UUID,
}

USER_2_TEST_SUBSCRIPTION_WATCH_USER_1 = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://test.example.com', 'method': 'get'},
    'events': ['test'],
    'owner_user_uuid': USER_2_UUID,
    'events_user_uuid': USER_1_UUID,
    'events_wazo_uuid': WAZO_UUID,
}

USER_SUBTENANT_TEST_SUBSCRIPTION = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://test.example.com', 'method': 'get'},
    'events': ['test'],
}

OTHER_USER_TEST_SUBSCRIPTION = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://test.example.com', 'method': 'get'},
    'events': ['test'],
    'owner_user_uuid': OTHER_USER_UUID,
    'owner_tenant_uuid': OTHER_TENANT,
    'events_user_uuid': OTHER_USER_UUID,
    'events_wazo_uuid': WAZO_UUID,
}

UNOWNED_USER_1_TEST_SUBSCRIPTION = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://test.example.com', 'method': 'get'},
    'events': ['test'],
    'events_user_uuid': USER_1_UUID,
}

INVALID_SUBSCRIPTION: dict[str, Any] = {}


class TestListSubscriptions(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = EverythingOkWaitStrategy()

    def test_given_wrong_auth_when_list_then_401(self):
        webhookd = self.make_webhookd('invalid-token')

        assert_that(
            calling(webhookd.subscriptions.list),
            raises(WebhookdError, has_property('status_code', 401)),
        )

    def test_given_no_subscriptions_when_list_then_empty(self):
        webhookd = self.make_webhookd(MASTER_TOKEN)

        response = webhookd.subscriptions.list()

        assert_that(response, has_entries({'items': empty(), 'total': 0}))

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_subscription_when_list_then_list_one(self, subscription_):
        webhookd = self.make_webhookd(MASTER_TOKEN)

        response = webhookd.subscriptions.list()

        assert_that(
            response,
            has_entries(
                {'items': contains_exactly(has_entries(**subscription_)), 'total': 1}
            ),
        )

    @subscription(TEST_SUBSCRIPTION)
    @subscription(TEST_SUBSCRIPTION_METADATA, track_test_name=False)
    def test_given_search_metadata_when_list_then_list_filtered(
        self, subscription_, subscription_metadata_
    ):
        webhookd = self.make_webhookd(MASTER_TOKEN)

        response = webhookd.subscriptions.list(
            search_metadata=TEST_SUBSCRIPTION_METADATA['metadata']
        )

        assert_that(
            response,
            has_entries(
                {'items': contains_exactly(has_entries(**TEST_SUBSCRIPTION_METADATA))}
            ),
        )


class TestListUserSubscriptions(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = EverythingOkWaitStrategy()

    @subscription(UNOWNED_USER_1_TEST_SUBSCRIPTION, tenant=USERS_TENANT)
    @subscription(USER_1_TEST_SUBSCRIPTION, tenant=USERS_TENANT)
    def test_given_subscriptions_when_user_list_then_list_only_subscriptions_of_this_user(
        self, _, user_subscription
    ):
        webhookd = self.make_webhookd(USER_1_TOKEN)

        response = webhookd.subscriptions.list_as_user()

        assert_that(
            response,
            has_entries(
                {
                    'items': contains_exactly(has_entries(**user_subscription)),
                    'total': 1,
                }
            ),
        )


class TestGetSubscriptions(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = EverythingOkWaitStrategy()

    def test_given_no_auth_server_when_get_subscription_then_503(self):
        more_than_auth_timeout = 12
        webhookd = self.make_webhookd(MASTER_TOKEN, timeout=more_than_auth_timeout)

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
        webhookd = self.make_webhookd(MASTER_TOKEN)

        assert_that(
            calling(webhookd.subscriptions.get).with_args(SOME_SUBSCRIPTION_UUID),
            raises(WebhookdError, has_property('status_code', 404)),
        )

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_subscription_when_get_http_subscription_then_return_the_subscription(
        self, subscription_
    ):
        webhookd = self.make_webhookd(MASTER_TOKEN)

        response = webhookd.subscriptions.get(subscription_['uuid'])

        assert_that(response, has_entries(subscription_))


class TestGetSubscriptionLogs(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = EverythingOkWaitStrategy()

    def test_given_no_auth_server_when_get_subscription_then_503(self):
        more_than_auth_timeout = 12
        webhookd = self.make_webhookd(MASTER_TOKEN, timeout=more_than_auth_timeout)

        with self.auth_stopped():
            assert_that(
                calling(webhookd.subscriptions.get_logs).with_args(
                    SOME_SUBSCRIPTION_UUID
                ),
                raises(WebhookdError, has_property('status_code', 503)),
            )

    def test_given_wrong_auth_when_get_subscription_then_401(self):
        webhookd = self.make_webhookd('invalid-token')

        assert_that(
            calling(webhookd.subscriptions.get_logs).with_args(SOME_SUBSCRIPTION_UUID),
            raises(WebhookdError, has_property('status_code', 401)),
        )

    def test_given_no_subscription_when_get_http_subscription_then_404(self):
        webhookd = self.make_webhookd(MASTER_TOKEN)

        assert_that(
            calling(webhookd.subscriptions.get_logs).with_args(SOME_SUBSCRIPTION_UUID),
            raises(WebhookdError, has_property('status_code', 404)),
        )

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_subscription_when_get_http_subscription_then_return_the_subscription(
        self, subscription_
    ):
        webhookd = self.make_webhookd(MASTER_TOKEN)

        response = webhookd.subscriptions.get_logs(subscription_['uuid'])

        assert_that(response, has_entries({'total': equal_to(0), 'items': empty()}))


class TestGetUserSubscriptions(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = EverythingOkWaitStrategy()

    @subscription(UNOWNED_USER_1_TEST_SUBSCRIPTION, tenant=USERS_TENANT)
    def test_given_non_user_subscription_when_user_get_http_subscription_then_404(
        self, subscription_
    ):
        webhookd = self.make_webhookd(USER_1_TOKEN)

        assert_that(
            calling(webhookd.subscriptions.get_as_user).with_args(
                subscription_['uuid']
            ),
            raises(WebhookdError, has_property('status_code', 404)),
        )

    @subscription(USER_1_TEST_SUBSCRIPTION, tenant=USERS_TENANT)
    def test_given_user_subscription_when_user_get_http_subscription_then_return_the_subscription(
        self, subscription_
    ):
        webhookd = self.make_webhookd(USER_1_TOKEN)

        response = webhookd.subscriptions.get_as_user(subscription_['uuid'])

        assert_that(response, has_entries(subscription_))


class TestCreateSubscriptions(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = EverythingOkWaitStrategy()

    def test_given_no_auth_server_when_create_subscription_then_503(self):
        more_than_auth_timeout = 12
        webhookd = self.make_webhookd(MASTER_TOKEN, timeout=more_than_auth_timeout)

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
        webhookd = self.make_webhookd(MASTER_TOKEN)

        assert_that(
            calling(webhookd.subscriptions.create).with_args(INVALID_SUBSCRIPTION),
            raises(WebhookdError, has_property('status_code', 400)),
        )

    def test_when_create_http_subscription_then_subscription_no_error(self):
        webhookd = self.make_webhookd(MASTER_TOKEN)

        response = webhookd.subscriptions.create(TEST_SUBSCRIPTION)
        subscription_uuid = response['uuid']

        assert_that(response, has_entries(owner_tenant_uuid=MASTER_TENANT))

        assert_that(response, has_key('uuid'))

        response = webhookd.subscriptions.list()
        assert_that(
            response, has_entry('items', has_item(has_entry('uuid', subscription_uuid)))
        )
        assert_that(
            response,
            has_entry('items', has_item(has_entry('owner_tenant_uuid', MASTER_TENANT))),
        )

    def given_metadata_when_create_subscription_then_metadata_are_attached(self):
        webhookd = self.make_webhookd(MASTER_TOKEN)

        response = webhookd.subscriptions.create(TEST_SUBSCRIPTION_METADATA)
        subscription_uuid = response['uuid']

        assert_that(response, has_key('uuid'))

        response = webhookd.subscriptions.get(subscription_uuid)
        assert_that(
            response, has_entry('metadata', TEST_SUBSCRIPTION_METADATA['metadata'])
        )


class TestCreateUserSubscriptions(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = EverythingOkWaitStrategy()

    def test_when_create_http_user_subscription_then_subscription_no_error(self):
        webhookd = self.make_webhookd(USER_1_TOKEN)

        response = webhookd.subscriptions.create_as_user(TEST_SUBSCRIPTION)

        assert_that(
            response,
            has_entries(
                {
                    'events_user_uuid': USER_1_UUID,
                    'events_wazo_uuid': WAZO_UUID,
                    'owner_user_uuid': USER_1_UUID,
                    'owner_tenant_uuid': USERS_TENANT,
                }
            ),
        )

        webhookd = self.make_webhookd(MASTER_TOKEN)
        response = webhookd.subscriptions.list(recurse=False)
        assert_that(response, has_entry('items', equal_to([])))

        response = webhookd.subscriptions.list(recurse=True)
        assert_that(
            response,
            has_entry('items', has_item(has_entry('owner_tenant_uuid', USERS_TENANT))),
        )

    def test_given_events_user_uuid_when_create_http_user_subscription_then_events_user_uuid_ignored(  # noqa: E501
        self,
    ):
        webhookd = self.make_webhookd(USER_1_TOKEN)

        response = webhookd.subscriptions.create_as_user(USER_1_TEST_SUBSCRIPTION)

        assert_that(
            response,
            has_entries(
                {
                    'events_user_uuid': USER_1_UUID,
                    'events_wazo_uuid': WAZO_UUID,
                    'owner_user_uuid': USER_1_UUID,
                    'owner_tenant_uuid': USERS_TENANT,
                }
            ),
        )

        webhookd = self.make_webhookd(MASTER_TOKEN)
        response = webhookd.subscriptions.list(recurse=False)
        assert_that(response, has_entry('items', equal_to([])))

        response = webhookd.subscriptions.list(recurse=True)
        assert_that(
            response,
            has_entry('items', has_item(has_entry('owner_tenant_uuid', USERS_TENANT))),
        )


class TestEditSubscriptions(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = EverythingOkWaitStrategy()

    def test_given_no_auth_server_when_edit_subscription_then_503(self):
        more_than_auth_timeout = 12
        webhookd = self.make_webhookd(MASTER_TOKEN, timeout=more_than_auth_timeout)

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
        webhookd = self.make_webhookd(MASTER_TOKEN)

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
        webhookd = self.make_webhookd(MASTER_TOKEN)

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
        webhookd = self.make_webhookd(MASTER_TOKEN)
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
        webhookd = self.make_webhookd(MASTER_TOKEN)
        subscription_uuid = subscription_['uuid']

        subscription_['metadata'] = {'new_key': 'new_value', 'another_new_key': 'value'}

        webhookd.subscriptions.update(subscription_uuid, subscription_)

        response = webhookd.subscriptions.get(subscription_['uuid'])
        assert_that(response, has_entry('metadata', subscription_['metadata']))


class TestEditUserSubscriptions(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = EverythingOkWaitStrategy()

    @subscription(UNOWNED_USER_1_TEST_SUBSCRIPTION, tenant=USERS_TENANT)
    def test_given_non_user_subscription_when_user_edit_http_subscription_then_404(
        self, subscription_
    ):
        webhookd = self.make_webhookd(USER_1_TOKEN)

        assert_that(
            calling(webhookd.subscriptions.update_as_user).with_args(
                subscription_['uuid'], ANOTHER_TEST_SUBSCRIPTION
            ),
            raises(WebhookdError, has_property('status_code', 404)),
        )

    @subscription(USER_1_TEST_SUBSCRIPTION, tenant=USERS_TENANT)
    def test_given_user_subscription_when_user_edit_http_subscription_then_updated(
        self, subscription_
    ):
        webhookd = self.make_webhookd(USER_1_TOKEN)
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
    wait_strategy = EverythingOkWaitStrategy()

    def test_given_no_auth_server_when_delete_subscription_then_503(self):
        more_than_auth_timeout = 12
        webhookd = self.make_webhookd(MASTER_TOKEN, timeout=more_than_auth_timeout)

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
        webhookd = self.make_webhookd(MASTER_TOKEN)

        assert_that(
            calling(webhookd.subscriptions.delete).with_args(SOME_SUBSCRIPTION_UUID),
            raises(WebhookdError, has_property('status_code', 404)),
        )

    @subscription(TEST_SUBSCRIPTION)
    def test_given_one_subscription_when_delete_http_subscription_then_deleted(
        self, subscription_
    ):
        webhookd = self.make_webhookd(MASTER_TOKEN)

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
    wait_strategy = EverythingOkWaitStrategy()

    @subscription(UNOWNED_USER_1_TEST_SUBSCRIPTION, tenant=USERS_TENANT)
    def test_given_non_user_subscription_when_user_delete_http_subscription_then_404(
        self, subscription_
    ):
        webhookd = self.make_webhookd(USER_1_TOKEN)

        assert_that(
            calling(webhookd.subscriptions.delete_as_user).with_args(
                subscription_['uuid']
            ),
            raises(WebhookdError, has_property('status_code', 404)),
        )

    @subscription(USER_1_TEST_SUBSCRIPTION, tenant=USERS_TENANT)
    def test_given_user_subscription_when_user_delete_http_subscription_then_deleted(
        self, subscription_
    ):
        webhookd = self.make_webhookd(USER_1_TOKEN)

        webhookd.subscriptions.delete_as_user(subscription_['uuid'])

        response = webhookd.subscriptions.list_as_user()
        assert_that(
            response,
            has_entry(
                'items', not_(has_item(has_entry('uuid', subscription_['uuid'])))
            ),
        )


class TestMultiTenantSubscriptions(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = EverythingOkWaitStrategy()

    @subscription(USER_SUBTENANT_TEST_SUBSCRIPTION, tenant=USERS_TENANT)
    def test_subscriptions_manipulate_with_user1(self, subscription_):
        webhookd = self.make_webhookd(USER_1_TOKEN)
        response = webhookd.subscriptions.list()
        assert_that(
            response,
            has_entry('items', has_item(has_entry('uuid', subscription_['uuid']))),
        )

        response = webhookd.subscriptions.get(subscription_['uuid'])
        assert_that(response, has_entry('uuid', subscription_['uuid']))

        subscription_["name"] = "update 1"
        response = webhookd.subscriptions.update(subscription_['uuid'], subscription_)
        assert_that(response, has_entry('uuid', subscription_['uuid']))
        assert_that(response, has_entry('name', subscription_['name']))

        webhookd.subscriptions.delete(subscription_['uuid'])
        self.ensure_webhookd_not_consume_subscription(subscription_)
        response = webhookd.subscriptions.list()
        assert_that(response, has_entry('items', equal_to([])))

        response = webhookd.subscriptions.create_as_user(subscription_)
        assert_that(response, has_entry('name', subscription_['name']))

        subscription_["uuid"] = response["uuid"]

        response = webhookd.subscriptions.get_as_user(subscription_['uuid'])
        assert_that(response, has_entry('uuid', subscription_['uuid']))

        subscription_["name"] = "update 2"
        response = webhookd.subscriptions.update_as_user(
            subscription_['uuid'], subscription_
        )
        assert_that(response, has_entry('uuid', subscription_['uuid']))
        assert_that(response, has_entry('name', subscription_['name']))

        webhookd.subscriptions.delete_as_user(subscription_['uuid'])
        self.ensure_webhookd_not_consume_subscription(subscription_)

    @subscription(USER_SUBTENANT_TEST_SUBSCRIPTION, tenant=USERS_TENANT)
    def test_subscriptions_manipulate_with_user2(self, subscription_):
        webhookd = self.make_webhookd(USER_2_TOKEN)
        response = webhookd.subscriptions.list()
        assert_that(
            response,
            has_entry('items', has_item(has_entry('uuid', subscription_['uuid']))),
        )

        response = webhookd.subscriptions.get(subscription_['uuid'])
        assert_that(response, has_entry('uuid', subscription_['uuid']))

        updated_name = "update 1"
        updated_subscription = subscription_.copy()
        updated_subscription["name"] = updated_name
        del updated_subscription["uuid"]
        response = webhookd.subscriptions.update(
            subscription_['uuid'], updated_subscription
        )
        assert_that(response, has_entry('uuid', subscription_['uuid']))
        assert_that(response, has_entry('name', updated_name))

        webhookd.subscriptions.delete(subscription_['uuid'])
        self.ensure_webhookd_not_consume_subscription(subscription_)
        response = webhookd.subscriptions.list()
        assert_that(response, has_entry('items', equal_to([])))

        webhookd = self.make_webhookd(USER_1_TOKEN)
        response = webhookd.subscriptions.create_as_user(subscription_)
        assert_that(response, has_entry('name', subscription_['name']))

        subscription_["uuid"] = response["uuid"]

        webhookd = self.make_webhookd(USER_2_TOKEN)
        assert_that(
            calling(webhookd.subscriptions.get_as_user).with_args(
                subscription_['uuid']
            ),
            raises(WebhookdError, has_property('status_code', 404)),
        )
        assert_that(
            calling(webhookd.subscriptions.update_as_user).with_args(
                subscription_['uuid'], subscription_
            ),
            raises(WebhookdError, has_property('status_code', 404)),
        )
        assert_that(
            calling(webhookd.subscriptions.delete_as_user).with_args(
                subscription_['uuid']
            ),
            raises(WebhookdError, has_property('status_code', 404)),
        )

    @subscription(USER_SUBTENANT_TEST_SUBSCRIPTION, tenant=USERS_TENANT)
    def test_subscriptions_list_tenant_with_token_not_in_tenant(self, subscription_):
        webhookd = self.make_webhookd(OTHER_USER_TOKEN)

        # Global
        response = webhookd.subscriptions.list()
        assert_that(response, has_entry('items', equal_to([])))

        response = webhookd.subscriptions.list(recurse=True)
        assert_that(response, has_entry('items', equal_to([])))

        assert_that(
            calling(webhookd.subscriptions.get).with_args(subscription_['uuid']),
            raises(WebhookdError, has_property('status_code', 404)),
        )
        assert_that(
            calling(webhookd.subscriptions.update).with_args(
                subscription_['uuid'], subscription_
            ),
            raises(WebhookdError, has_property('status_code', 404)),
        )
        assert_that(
            calling(webhookd.subscriptions.delete).with_args(subscription_['uuid']),
            raises(WebhookdError, has_property('status_code', 404)),
        )

        # As User
        response = webhookd.subscriptions.list_as_user()
        assert_that(response, has_entry('items', equal_to([])))

        assert_that(
            calling(webhookd.subscriptions.get_as_user).with_args(
                subscription_['uuid']
            ),
            raises(WebhookdError, has_property('status_code', 404)),
        )
        assert_that(
            calling(webhookd.subscriptions.update_as_user).with_args(
                subscription_['uuid'], subscription_
            ),
            raises(WebhookdError, has_property('status_code', 404)),
        )
        assert_that(
            calling(webhookd.subscriptions.delete_as_user).with_args(
                subscription_['uuid']
            ),
            raises(WebhookdError, has_property('status_code', 404)),
        )

    @subscription(USER_SUBTENANT_TEST_SUBSCRIPTION, tenant=USERS_TENANT)
    def test_subscriptions_manipulate_with_parent_token_and_parent_tenant(
        self, subscription_
    ):
        webhookd = self.make_webhookd(MASTER_TOKEN)
        response = webhookd.subscriptions.list()
        assert_that(response, has_entry('items', equal_to([])))

        response = webhookd.subscriptions.list(recurse=True)
        assert_that(
            response,
            has_entry('items', has_item(has_entry('uuid', subscription_['uuid']))),
        )

        response = webhookd.subscriptions.get(subscription_['uuid'])
        assert_that(response, has_entry('uuid', subscription_['uuid']))

        subscription_["name"] = "update"
        response = webhookd.subscriptions.update(subscription_['uuid'], subscription_)
        assert_that(response, has_entry('uuid', subscription_['uuid']))
        assert_that(response, has_entry('name', subscription_['name']))

        webhookd.subscriptions.delete(subscription_['uuid'])
        self.ensure_webhookd_not_consume_subscription(subscription_)
        response = webhookd.subscriptions.list()
        assert_that(response, has_entry('items', equal_to([])))

    @subscription(USER_SUBTENANT_TEST_SUBSCRIPTION, tenant=USERS_TENANT)
    def test_subscriptions_manipulate_with_parent_token_and_users_tenant(
        self, subscription_
    ):
        webhookd = self.make_webhookd(MASTER_TOKEN, USERS_TENANT)
        response = webhookd.subscriptions.list()
        assert_that(
            response,
            has_entry('items', has_item(has_entry('uuid', subscription_['uuid']))),
        )

        response = webhookd.subscriptions.list(recurse=True)
        assert_that(
            response,
            has_entry('items', has_item(has_entry('uuid', subscription_['uuid']))),
        )

        response = webhookd.subscriptions.get(subscription_['uuid'])
        assert_that(response, has_entry('uuid', subscription_['uuid']))
        assert_that(response, has_entry('owner_tenant_uuid', USERS_TENANT))

        subscription_["name"] = "update"
        response = webhookd.subscriptions.update(subscription_['uuid'], subscription_)
        assert_that(response, has_entry('uuid', subscription_['uuid']))
        assert_that(response, has_entry('name', subscription_['name']))
        assert_that(response, has_entry('owner_tenant_uuid', USERS_TENANT))

        webhookd.subscriptions.delete(subscription_['uuid'])
        self.ensure_webhookd_not_consume_subscription(subscription_)
        response = webhookd.subscriptions.list()
        assert_that(response, has_entry('items', equal_to([])))


class TestSubscriptionCleanup(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = EverythingOkWaitStrategy()

    def setUp(self):
        super().setUp()
        self.bus = self.make_bus()

    @subscription(USER_1_TEST_SUBSCRIPTION, tenant=USERS_TENANT)
    @subscription(USER_2_TEST_SUBSCRIPTION, tenant=USERS_TENANT)
    @subscription(USER_2_TEST_SUBSCRIPTION_WATCH_USER_1, tenant=USERS_TENANT)
    def test_subscription_auto_delete_on_user_deleted(
        self, subscription_1, subscription_2, subscription_3
    ):
        webhookd = self.make_webhookd(MASTER_TOKEN)
        response = webhookd.subscriptions.list(recurse=True)
        subscription_uuids = {item['uuid'] for item in response['items']}
        assert subscription_1['uuid'] in subscription_uuids
        assert subscription_2['uuid'] in subscription_uuids
        assert subscription_3['uuid'] in subscription_uuids

        event = {
            'name': 'user_deleted',
            'data': {'uuid': USER_1_UUID},
        }
        self.bus.publish(
            event, routing_key=SOME_ROUTING_KEY, headers={'name': event['name']}
        )

        def user_subscription_deleted():
            response = webhookd.subscriptions.list(recurse=True)
            subscription_uuids = {item['uuid'] for item in response['items']}
            assert subscription_1['uuid'] not in subscription_uuids
            assert subscription_2['uuid'] in subscription_uuids
            assert subscription_3['uuid'] not in subscription_uuids

        until.assert_(
            user_subscription_deleted,
            timeout=5,
            message='User subscription not deleted',
        )

    @subscription(USER_1_TEST_SUBSCRIPTION, tenant=USERS_TENANT)
    @subscription(OTHER_USER_TEST_SUBSCRIPTION, tenant=OTHER_TENANT)
    def test_subscription_auto_delete_on_tenant_deleted(
        self, subscription_1, subscription_2
    ):
        webhookd = self.make_webhookd(MASTER_TOKEN)
        response = webhookd.subscriptions.list(recurse=True)
        subscription_uuids = {item['uuid'] for item in response['items']}
        assert subscription_1['uuid'] in subscription_uuids
        assert subscription_2['uuid'] in subscription_uuids

        event = {
            'name': 'auth_tenant_deleted',
            'data': {'uuid': OTHER_TENANT},
        }
        self.bus.publish(
            event, routing_key=SOME_ROUTING_KEY, headers={'name': event['name']}
        )

        def tenant_subscription_deleted():
            response = webhookd.subscriptions.list(recurse=True)
            subscription_uuids = {item['uuid'] for item in response['items']}
            assert subscription_1['uuid'] in subscription_uuids
            assert subscription_2['uuid'] not in subscription_uuids

        until.assert_(
            tenant_subscription_deleted,
            timeout=5,
            message='Tenant subscription not deleted',
        )


class TestSubscriptionEvents(SubscriptionFixtureMixin, BaseIntegrationTest):
    asset = 'base'
    wait_strategy = EverythingOkWaitStrategy()

    def setUp(self):
        super().setUp()
        self.bus = self.make_bus()

    def test_subscription_created_event(self):
        accumulator = self.bus.accumulator(
            headers={'name': 'webhookd_subscription_created', 'user_uuid:*': True},
        )

        with self.subscription(TEST_SUBSCRIPTION) as subscription_:
            assert_that(subscription_, has_entry('uuid', instance_of(str)))

            events = accumulator.accumulate(with_headers=True)
            assert_that(events, has_length(1))

            assert_that(
                events,
                contains_inanyorder(
                    has_entries(
                        message=has_entries(
                            data=has_entries(
                                uuid=subscription_['uuid'],
                                owner_tenant_uuid=MASTER_TENANT,
                                **TEST_SUBSCRIPTION,
                            ),
                        )
                    )
                ),
            )

    def test_user_subscription_created_event(self):
        accumulator = self.bus.accumulator(
            headers={
                'name': 'webhookd_user_subscription_created',
                f'user_uuid:{USER_1_UUID}': True,
            },
        )

        with self.user_subscription(
            TEST_SUBSCRIPTION, token=USER_1_TOKEN
        ) as subscription_:
            assert_that(subscription_, has_entry('uuid', instance_of(str)))

            events = accumulator.accumulate(with_headers=True)
            assert_that(events, has_length(1))

            assert_that(
                events,
                contains_inanyorder(
                    has_entries(
                        message=has_entries(
                            data=has_entries(
                                name=subscription_['name'],
                                service=subscription_['service'],
                                events=subscription_['events'],
                                config=has_entries(subscription_['config']),
                            ),
                        ),
                        headers=has_entries(
                            {
                                f'user_uuid:{USER_1_UUID}': True,
                                'name': 'webhookd_user_subscription_created',
                                'tenant_uuid': USERS_TENANT,
                            }
                        ),
                    )
                ),
            )

    @subscription(TEST_SUBSCRIPTION)
    def test_subscription_updated_event(self, subscription_):
        webhookd = self.make_webhookd(MASTER_TOKEN)

        accumulator = self.bus.accumulator(
            headers={'name': 'webhookd_subscription_updated', 'user_uuid:*': True},
        )

        # Update the subscription
        updated_subscription = dict(subscription_)
        updated_subscription['name'] = 'updated_test'
        webhookd.subscriptions.update(
            updated_subscription.pop('uuid'), updated_subscription
        )

        events = accumulator.accumulate(with_headers=True)
        assert_that(events, has_length(1))

        assert_that(
            events,
            contains_inanyorder(
                has_entries(
                    message=has_entries(
                        data=has_entries(updated_subscription),
                    ),
                    headers=has_entries(
                        {
                            'name': 'webhookd_subscription_updated',
                            'tenant_uuid': MASTER_TENANT,
                        }
                    ),
                )
            ),
        )

    @user_subscription(
        USER_1_TEST_SUBSCRIPTION, token=USER_1_TOKEN, tenant=USERS_TENANT
    )
    def test_user_subscription_updated_event(self, subscription_):
        webhookd = self.make_webhookd(USER_1_TOKEN)

        accumulator = self.bus.accumulator(
            headers={
                'name': 'webhookd_user_subscription_updated',
                f'user_uuid:{USER_1_UUID}': True,
            },
        )

        # Update the subscription
        updated_subscription = dict(subscription_)
        updated_subscription['name'] = 'updated_test'
        webhookd.subscriptions.update_as_user(
            updated_subscription.pop('uuid'), updated_subscription
        )

        events = accumulator.accumulate(with_headers=True)
        assert_that(events, has_length(1))

        assert_that(
            events,
            contains_inanyorder(
                has_entries(
                    message=has_entries(
                        data=has_entries(
                            name='updated_test',
                            service=subscription_['service'],
                            events=subscription_['events'],
                            config=has_entries(subscription_['config']),
                        ),
                    ),
                    headers=has_entries(
                        {
                            f'user_uuid:{USER_1_UUID}': True,
                            'name': 'webhookd_user_subscription_updated',
                            'tenant_uuid': USERS_TENANT,
                        }
                    ),
                )
            ),
        )

    @subscription(TEST_SUBSCRIPTION, auto_delete=False)
    def test_subscription_deleted_event(self, subscription_):
        webhookd = self.make_webhookd(MASTER_TOKEN)

        accumulator = self.bus.accumulator(
            headers={'name': 'webhookd_subscription_deleted', 'user_uuid:*': True},
        )

        # Delete the subscription
        webhookd.subscriptions.delete(subscription_['uuid'])

        events = accumulator.accumulate(with_headers=True)
        assert_that(events, has_length(1))

        assert_that(
            events,
            contains_inanyorder(
                has_entries(
                    message=has_entries(
                        data=has_entries(subscription_),
                    ),
                    headers=has_entries(
                        {
                            'name': 'webhookd_subscription_deleted',
                            'tenant_uuid': MASTER_TENANT,
                        }
                    ),
                )
            ),
        )

    @user_subscription(
        USER_1_TEST_SUBSCRIPTION,
        token=USER_1_TOKEN,
        tenant=USERS_TENANT,
        auto_delete=False,
    )
    def test_user_subscription_deleted_event(self, subscription_):
        webhookd = self.make_webhookd(USER_1_TOKEN)

        accumulator = self.bus.accumulator(
            headers={
                'name': 'webhookd_user_subscription_deleted',
                f'user_uuid:{USER_1_UUID}': True,
            },
        )

        # Delete the subscription
        webhookd.subscriptions.delete_as_user(subscription_['uuid'])

        events = accumulator.accumulate(with_headers=True)
        assert_that(events, has_length(1))

        assert_that(
            events,
            contains_inanyorder(
                has_entries(
                    message=has_entries(
                        data=has_entries(
                            name=subscription_['name'],
                            service=subscription_['service'],
                            events=subscription_['events'],
                            config=has_entries(subscription_['config']),
                        ),
                    ),
                    headers=has_entries(
                        {
                            f'user_uuid:{USER_1_UUID}': True,
                            'name': 'webhookd_user_subscription_deleted',
                            'tenant_uuid': USERS_TENANT,
                        }
                    ),
                )
            ),
        )
