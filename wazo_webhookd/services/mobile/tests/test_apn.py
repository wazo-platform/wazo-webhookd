# Copyright 2022-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from typing import Any
from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import sentinel as s

from hamcrest import assert_that, equal_to

from wazo_webhookd.services.mobile.plugin import (
    NotificationPayload,
    NotificationType,
    PushNotification,
)


class TestAPN(TestCase):
    def setUp(self):
        self.task = Mock()
        self.config = {
            'mobile_apns_host': 'api.push.apple.com',
            'mobile_apns_port': 443,
            'mobile_apns_call_topic': 'org.wazo-platform.voip',
            'mobile_apns_default_topic': 'org.wazo-platform',
        }
        self.external_tokens = {
            'apns_voip_token': s.apns_voip_token,
            'apns_notification_token': s.apns_notification_token,
        }
        self.external_config: dict[str, Any] = {}
        self.jwt = ''
        self._push = PushNotification(
            self.task,
            self.config,  # type: ignore
            self.external_tokens,  # type: ignore
            self.external_config,  # type: ignore
            self.jwt,
        )

    def test_wazo_notification_call(self):
        message_title = None
        message_body = None
        data: NotificationPayload = {
            'notification_type': NotificationType.INCOMING_CALL,
            'items': {},
        }

        headers, payload, token = self._push._create_apn_message(
            message_title,
            message_body,
            data,
            False,
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
                    'aps': {'alert': data, 'badge': 1},
                    'notification_type': NotificationType.INCOMING_CALL,
                    'items': {},
                }
            ),
        )
        assert_that(token, equal_to(s.apns_voip_token))

    def test_wazo_cancel_notification(self):
        message_title = None
        message_body = None
        data: NotificationPayload = {
            'notification_type': NotificationType.CANCEL_INCOMING_CALL,
            'items': {},
        }

        headers, payload, token = self._push._create_apn_message(
            message_title,
            message_body,
            data,
            False,
        )

        assert_that(
            headers,
            equal_to(
                {
                    'apns-topic': 'org.wazo-platform',
                    'apns-push-type': 'alert',
                    'apns-priority': '5',
                }
            ),
        )
        assert_that(
            payload,
            equal_to(
                {
                    'aps': {"badge": 1, "sound": "default", "content-available": 1},
                    'notification_type': NotificationType.CANCEL_INCOMING_CALL,
                    'items': {},
                }
            ),
        )
        assert_that(token, equal_to(s.apns_notification_token))

    def test_wazo_message_received(self):
        data: NotificationPayload = {
            'notification_type': NotificationType.MESSAGE_RECEIVED,
            'items': {
                'message': 'Hello',
                'room_uuid': '1234567890',
                'user_uuid': '1234567890',
                'tenant_uuid': '1234567890',
                'alias': 'John Doe',
            },
        }

        headers, payload, token = self._push._create_apn_message(
            None,
            None,
            data,
            True,
        )

        assert_that(
            headers,
            equal_to(
                {
                    'apns-topic': 'org.wazo-platform',
                    'apns-push-type': 'alert',
                    'apns-priority': '5',
                }
            ),
        )
        assert_that(
            payload,
            equal_to(
                {
                    'aps': {"badge": 1, "sound": "default", "content-available": 1},
                    'data': {
                        'notification_type': NotificationType.MESSAGE_RECEIVED,
                        'items': data['items'],
                    },
                }
            ),
        )
        assert_that(token, equal_to(s.apns_notification_token))
