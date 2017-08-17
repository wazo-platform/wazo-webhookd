# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from collections import defaultdict
from hamcrest import assert_that
from hamcrest import equal_to
from hamcrest import is_
from mock import Mock
from unittest import TestCase

from ..bus import SubscriptionBusEventHandler


class TestBusEventHandler(TestCase):

    def test_given_one_non_http_subscription_when_event_then_no_http_callback(self):
        task = Mock()
        celery = Mock()
        celery.tasks = defaultdict(lambda: task)
        subscription_config = {
            'url': 'http://callback-handler',
            'method': 'get'
        }
        subscription = Mock(service='non-http', events=['trigger'], config=subscription_config)
        service = Mock()
        service.list.return_value = [subscription]
        handler = SubscriptionBusEventHandler(celery, service)

        handler.on_wazo_event({'name': 'trigger'})

        assert_that(task.apply_async.called, is_(False))

    def test_given_two_http_subscription_when_event_then_two_http_callback(self):
        task = Mock()
        celery = Mock()
        service = Mock()
        handler = SubscriptionBusEventHandler(celery, service)
        celery.tasks = defaultdict(lambda: task)
        subscription_config = {
            'url': 'http://callback-handler',
            'method': 'get'
        }
        subscription = Mock(service='http', config=subscription_config, events=['trigger'])
        service.list.return_value = [subscription] * 2

        handler.on_wazo_event({'name': 'trigger'})

        assert_that(task.apply_async.call_count, equal_to(2))

    def test_given_http_subscription_when_two_events_then_two_http_callback(self):
        task = Mock()
        celery = Mock()
        service = Mock()
        handler = SubscriptionBusEventHandler(celery, service)
        celery.tasks = defaultdict(lambda: task)
        subscription_config = {
            'url': 'http://callback-handler',
            'method': 'get'
        }
        subscription = Mock(service='http', config=subscription_config, events=['trigger'])
        service.list.return_value = [subscription]

        handler.on_wazo_event({'name': 'trigger'})
        handler.on_wazo_event({'name': 'trigger'})

        assert_that(task.apply_async.call_count, equal_to(2))

    def test_given_http_subscription_when_non_triggering_event_then_no_http_callback(self):
        task = Mock()
        celery = Mock()
        service = Mock()
        handler = SubscriptionBusEventHandler(celery, service)
        celery.tasks = defaultdict(lambda: task)
        subscription_config = {
            'url': 'http://callback-handler',
            'method': 'get'
        }
        subscription = Mock(service='http', config=subscription_config, events=['trigger'])
        service.list.return_value = [subscription]

        handler.on_wazo_event({'name': 'no-trigger'})

        assert_that(task.apply_async.called, is_(False))

    def test_given_http_subscription_with_body_when_event_then_http_callback_with_body(self):
        task = Mock()
        celery = Mock()
        service = Mock()
        handler = SubscriptionBusEventHandler(celery, service)
        celery.tasks = defaultdict(lambda: task)
        subscription_config = {
            'url': 'http://callback-handler',
            'method': 'get',
            'body': 'my-body',
        }
        subscription = Mock(service='http', config=subscription_config, events=['trigger'])
        service.list.return_value = [subscription]

        handler.on_wazo_event({'name': 'trigger'})

        task.apply_async.assert_called_once_with(['get', 'http://callback-handler', 'my-body', None])
