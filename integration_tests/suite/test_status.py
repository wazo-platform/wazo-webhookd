# Copyright 2017-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from contextlib import contextmanager

from hamcrest import assert_that, equal_to, has_entries
from wazo_test_helpers import until
from wazo_test_helpers.auth import MockCredentials

from .helpers.base import MASTER_TOKEN, START_TIMEOUT, BaseIntegrationTest
from .helpers.wait_strategy import (
    EverythingOkWaitStrategy,
    NoWaitStrategy,
    WebhookdStartedWaitStrategy,
)


class TestStatusRabbitMQStops(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def test_given_rabbitmq_stops_when_status_then_bus_consumer_status_fail(self):
        webhookd = self.make_webhookd(MASTER_TOKEN)

        def all_connections_ok():
            result = webhookd.status.get()
            assert_that(result['bus_consumer'], has_entries({'status': 'ok'}))

        until.assert_(all_connections_ok, timeout=20)

        def rabbitmq_is_down():
            result = webhookd.status.get()
            assert_that(result['bus_consumer']['status'], equal_to('fail'))

        with self.rabbitmq_stopped():
            until.assert_(rabbitmq_is_down, timeout=10)


class TestStatusBindingsFailing(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = EverythingOkWaitStrategy()

    @contextmanager
    def headers_exchange_unreadable(self):
        self.set_guest_read_permission('^(?!wazo-headers$).*')
        try:
            yield
        finally:
            self.set_guest_read_permission('.*')

    def set_guest_read_permission(self, read):
        command = ['rabbitmqctl', 'set_permissions', 'guest', '.*', '.*', read]
        self.docker_exec(command, service_name='rabbitmq')

    def test_given_upstream_bind_refused_when_subscribe_then_bus_consumer_status_fail(
        self,
    ):
        webhookd = self.make_webhookd(MASTER_TOKEN)

        def bus_consumer_status(expected):
            result = webhookd.status.get()
            assert_that(result['bus_consumer']['status'], equal_to(expected))

        with self.headers_exchange_unreadable():
            webhookd.subscriptions.create(
                {
                    'name': 'test',
                    'service': 'http',
                    'config': {
                        'url': 'http://third-party-http:1080/test',
                        'method': 'get',
                    },
                    'events': ['failing_upstream_event'],
                }
            )
            until.assert_(bus_consumer_status, 'fail', timeout=10)

        until.assert_(bus_consumer_status, 'ok', timeout=10)


class TestStatusAllOK(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def test_given_rabbitmq_when_status_then_status_ok(self):
        webhookd = self.make_webhookd(MASTER_TOKEN)

        def all_connections_ok():
            result = webhookd.status.get()
            assert_that(
                result,
                has_entries(
                    bus_consumer=has_entries(status='ok'),
                    master_tenant=has_entries(status='ok'),
                ),
            )

        until.assert_(all_connections_ok, timeout=20)


class TestStatusPluginProvider(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = EverythingOkWaitStrategy()

    def test_plugin_status_provider_appears_in_response(self):
        webhookd = self.make_webhookd(MASTER_TOKEN)

        result = webhookd.status.get()
        assert_that(
            result,
            has_entries(
                bus_consumer=has_entries(status='ok'),
                master_tenant=has_entries(status='ok'),
                test_component=has_entries(status='ok'),
            ),
        )


class TestStatusNoMasterTenant(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = EverythingOkWaitStrategy()

    def test_before_master_tenant_initialization(self):
        auth = self.make_auth()
        auth.set_invalid_credentials(
            MockCredentials('webhookd-service', 'webhookd-password')
        )

        # clear existing master tenant token
        self.restart_service('webhookd')
        webhookd = self.make_webhookd(MASTER_TOKEN)
        WebhookdStartedWaitStrategy().wait(webhookd)

        def master_tenant_is_not_set():
            result = webhookd.status.get()
            assert_that(
                result,
                has_entries(
                    master_tenant=has_entries(status='fail'),
                ),
            )

        until.assert_(master_tenant_is_not_set, timeout=10)

        # restore wazo-webhookd credentials
        self.restart_service('auth')
        auth = self.make_auth()
        until.true(auth.is_up, timeout=START_TIMEOUT)
        self.configured_wazo_auth()

        def master_tenant_ok():
            result = webhookd.status.get()
            assert_that(
                result,
                has_entries(
                    master_tenant=has_entries(status='ok'),
                ),
            )

        until.assert_(master_tenant_ok, timeout=20)
