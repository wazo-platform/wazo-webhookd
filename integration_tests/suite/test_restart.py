# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import time
import uuid
from threading import Thread

import docker as docker_client
import requests
from hamcrest import assert_that, empty, equal_to, has_entries, is_not, less_than
from mockserver import MockServerClient
from wazo_test_helpers import until

from .helpers.base import MASTER_TENANT, MASTER_TOKEN, BaseIntegrationTest
from .helpers.wait_strategy import ConnectedWaitStrategy

EVENT = 'call_push_notification'
USERS_BEFORE = 40
USERS_DURING = 20


def push_subscription(user_uuid):
    return {
        'name': f'push {user_uuid}',
        'service': 'http',
        'config': {
            'url': f'http://third-party-http:1080/push/{user_uuid}',
            'method': 'post',
        },
        'events': [EVENT],
        'events_user_uuid': user_uuid,
    }


class TestSubscriptionsSurviveARestart(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = ConnectedWaitStrategy()

    def setUp(self):
        super().setUp()
        self.third_party = MockServerClient(
            f'http://127.0.0.1:{self.service_port(1080, "third-party-http")}'
        )
        self.third_party.reset()
        self.bus = self.make_bus()

    def _create(self, user_uuid):
        webhookd = self.make_webhookd(MASTER_TOKEN, tenant=MASTER_TENANT)
        return webhookd.subscriptions.create(push_subscription(user_uuid))

    def _create_once_up(self, user_uuid):
        try:
            return self._create(user_uuid)
        except requests.RequestException:
            return None

    def _stop_webhookd_seconds(self):
        docker = docker_client.from_env(timeout=60).api
        container_id = self._container_id('webhookd')
        started = time.monotonic()
        docker.stop(container_id, timeout=30)
        seconds = time.monotonic() - started
        exit_code = docker.inspect_container(container_id)['State']['ExitCode']
        return seconds, exit_code

    def test_restart_while_subscriptions_are_created_binds_everything(self):
        users = [str(uuid.uuid4()) for _ in range(USERS_BEFORE + USERS_DURING)]
        for user_uuid in users:
            self.third_party.mock_simple_response(
                path=f'/push/{user_uuid}', responseBody='ok', statusCode=200
            )
        for user_uuid in users[:USERS_BEFORE]:
            self._create(user_uuid)

        seconds, exit_code = self._stop_webhookd_seconds()
        assert_that(seconds, less_than(15))
        assert_that(exit_code, is_not(137))  # 137: killed after the timeout

        self.start_service('webhookd')
        failures = []

        def create_during_start():
            for user_uuid in users[USERS_BEFORE:]:
                try:
                    until.true(
                        lambda u=user_uuid: self._create_once_up(u),
                        timeout=60,
                        interval=0.2,
                    )
                except Exception as exc:  # reported below
                    failures.append(repr(exc))

        creator = Thread(target=create_during_start)
        creator.start()
        creator.join()
        assert_that(failures, empty())

        webhookd = self.make_webhookd(MASTER_TOKEN)

        def all_bound():
            try:
                status = webhookd.status.get()
            except requests.RequestException:
                raise AssertionError('wazo-webhookd is not up yet')
            subscriptions = status['subscriptions']
            assert_that(subscriptions['bound'], equal_to(subscriptions['desired']))
            assert_that(subscriptions, has_entries(queue_bindings_synced=True))

        until.assert_(all_bound, timeout=120, interval=1)

        for user_uuid in users:
            self.bus.publish(
                {
                    'name': EVENT,
                    'origin_uuid': 'my-origin-uuid',
                    'data': {'user_uuid': user_uuid},
                },
                headers={'name': EVENT, f'user_uuid:{user_uuid}': True},
            )

        def every_user_ran_its_hook():
            for user_uuid in users:
                self.third_party.verify(
                    request={'method': 'POST', 'path': f'/push/{user_uuid}'},
                    count=1,
                    exact=True,
                )

        until.assert_(_as_assertion(every_user_ran_its_hook), timeout=60, interval=1)


def _as_assertion(verify):
    def callback():
        try:
            verify()
        except Exception as exc:
            if str(exc) == 'Failed to verify':
                raise AssertionError()
            raise

    return callback
