# Copyright 2017-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that, has_entries
from requests import RequestException
from xivo_test_helpers import until


class WaitStrategy:
    def wait(self, webhookd):
        raise NotImplementedError()


class NoWaitStrategy(WaitStrategy):
    def wait(self, webhookd):
        pass


class InitializedWaitStrategy(WaitStrategy):
    def wait(self, webhookd):
        def webhookd_is_initialized():
            try:
                webhookd.config.get()
            except RequestException as e:
                raise AssertionError(e)

        until.assert_(webhookd_is_initialized, timeout=30, interval=1)


class ConnectedWaitStrategy(WaitStrategy):
    def wait(self, webhookd):
        def webhookd_is_connected():
            try:
                status = webhookd.status.get()
            except RequestException:
                raise AssertionError('wazo-webhookd is not up yet')
            assert_that(status['bus_consumer'], has_entries({'status': 'ok'}))

        until.assert_(webhookd_is_connected, timeout=30, interval=1)
