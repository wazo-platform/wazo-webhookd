# Copyright 2017-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that, empty, has_entries, not_
from requests import RequestException
from wazo_test_helpers import until


class WaitStrategy:
    def wait(self, webhookd):
        raise NotImplementedError()


class NoWaitStrategy(WaitStrategy):
    def wait(self, webhookd):
        pass


class EverythingOkWaitStrategy(WaitStrategy):
    def wait(self, webhookd):
        def is_ready():
            try:
                status = webhookd.status.get()
            except RequestException:
                status = {}

            assert_that(
                status,
                has_entries(
                    bus_consumer=has_entries(status='ok'),
                    master_tenant=has_entries(status='ok'),
                ),
            )

        until.assert_(is_ready, tries=60)


class WebhookdStartedWaitStrategy(WaitStrategy):
    def wait(self, webhookd):
        def is_ready():
            try:
                status = webhookd.status.get()
            except RequestException:
                status = {}

            assert_that(status, not_(empty()))

        until.assert_(is_ready, tries=30)


class ConnectedWaitStrategy(WaitStrategy):
    def wait(self, webhookd):
        def webhookd_is_connected():
            try:
                status = webhookd.status.get()
            except RequestException:
                raise AssertionError('wazo-webhookd is not up yet')
            assert_that(status['bus_consumer'], has_entries({'status': 'ok'}))

        until.assert_(webhookd_is_connected, timeout=30, interval=1)
