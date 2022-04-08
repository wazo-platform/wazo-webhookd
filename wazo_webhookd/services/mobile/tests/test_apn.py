# Copyright 2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from unittest import TestCase
from unittest.mock import Mock, sentinel as s
from hamcrest import assert_that, equal_to

from wazo_webhookd.services.mobile.plugin import PushNotification


class TestAPN(TestCase):
    def setUp(self):
        self.task = Mock()
        self.config = {}
        self.external_tokens = {
            'apns_voip_token': s.apns_voip_token,
            'apns_notification_token': s.apns_notification_token,
        }
        self.external_config = {}
        self.jwt = {}
        self._push = PushNotification(
            self.task,
            self.config,
            self.external_tokens,
            self.external_config,
            self.jwt,
        )

    def test_wazo_notification_call(self):
        message_title = None
        message_body = None
        channel_id = 'wazo-notification-call'
        data = {'my': 'event'}

        headers, payload, token = self._push._create_apn_message(
            message_title,
            message_body,
            channel_id,
            data,
        )

        assert_that(
            headers,
            equal_to(
                {
                    'apns-topic': 'org.wazo-platform.voip',
                    'apns-push-type': 'voip',
                    'apns-priority': '10',
                }
            ),
        )
        assert_that(
            payload,
            equal_to(
                {
                    'my': 'event',
                    'aps': {'alert': data, 'badge': 1},
                }
            ),
        )
        assert_that(token, equal_to(s.apns_voip_token))

    def test_wazo_cancel_notification(self):
        message_title = None
        message_body = None
        channel_id = 'wazo-notification-cancel-call'
        data = {'my': 'event'}

        headers, payload, token = self._push._create_apn_message(
            message_title,
            message_body,
            channel_id,
            data,
        )

        assert_that(
            headers,
            equal_to(
                {
                    'apns-topic': 'org.wazo-platform.voip',
                    'apns-push-type': 'alert',
                    'apns-priority': '5',
                }
            ),
        )
        assert_that(
            payload,
            equal_to(
                {
                    'my': 'event',
                    'aps': {"badge": 1, "sound": "default", "content-available": 1},
                }
            ),
        )
        assert_that(token, equal_to(s.apns_notification_token))
