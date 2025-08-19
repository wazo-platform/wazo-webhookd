# Copyright 2022-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from unittest import TestCase
from unittest.mock import Mock, patch
from unittest.mock import sentinel as s

from ..plugin import (
    DEFAULT_ANDROID_CHANNEL_ID,
    NotificationPayload,
    NotificationType,
    PushNotification,
)


class TestSendViaFcmLegacy(TestCase):
    def setUp(self):
        task = Mock()
        config = {
            'mobile_fcm_notification_end_point': 'the url',
        }
        external_tokens = {'token': s.token}
        external_config = {'fcm_api_key': s.fcm_api_key}
        jwt = Mock()

        self.push_notification = PushNotification(
            task,
            config,  # type: ignore
            external_tokens,  # type: ignore
            external_config,  # type: ignore
            jwt,
        )

    @patch('wazo_webhookd.services.mobile.plugin.FCMNotificationLegacy')
    def test_send_incoming_call(self, FCMNotificationLegacy):
        push_service = FCMNotificationLegacy.return_value

        title = 'Incoming Call'  # Ignored
        body = 'From: 5555555555'  # Ignored
        data: NotificationPayload = {
            'notification_type': NotificationType.INCOMING_CALL,
            'items': '',
        }

        self.push_notification._send_via_fcm(title, body, data, data_only=False)

        assert push_service.FCM_END_POINT == FCMNotificationLegacy.FCM_END_POINT
        FCMNotificationLegacy.assert_called_once_with(api_key=s.fcm_api_key)
        push_service.single_device_data_message.assert_not_called()
        push_service.notify_single_device.assert_called_once_with(
            low_priority=False,
            registration_id=s.token,
            data_message=data,
            time_to_live=0,
        )

    @patch('wazo_webhookd.services.mobile.plugin.FCMNotificationLegacy')
    def test_send_incoming_call_cancel(self, FCMNotificationLegacy):
        push_service = FCMNotificationLegacy.return_value

        title = None  # Ignored
        body = None  # Ignored
        data: NotificationPayload = {
            'notification_type': NotificationType.CANCEL_INCOMING_CALL,
            'items': '',
        }

        self.push_notification._send_via_fcm(title, body, data, data_only=False)

        assert push_service.FCM_END_POINT == FCMNotificationLegacy.FCM_END_POINT
        FCMNotificationLegacy.assert_called_once_with(api_key=s.fcm_api_key)
        push_service.single_device_data_message.assert_called_once_with(
            registration_id=s.token,
            data_message=data,
            time_to_live=0,
            android_channel_id=DEFAULT_ANDROID_CHANNEL_ID,
        )
        push_service.notify_single_device.assert_not_called()

    @patch('wazo_webhookd.services.mobile.plugin.FCMNotificationLegacy')
    def test_send_voicemail_received(self, FCMNotificationLegacy):
        push_service = FCMNotificationLegacy.return_value

        title = 'New voicemail'
        body = 'From: 5555555555'
        data: NotificationPayload = {
            'notification_type': NotificationType.VOICEMAIL_RECEIVED,
            'items': '',
        }

        self.push_notification._send_via_fcm(title, body, data, data_only=False)

        assert push_service.FCM_END_POINT == FCMNotificationLegacy.FCM_END_POINT
        FCMNotificationLegacy.assert_called_once_with(api_key=s.fcm_api_key)
        push_service.single_device_data_message.assert_not_called()
        push_service.notify_single_device.assert_called_once_with(
            registration_id=s.token,
            data_message=data,
            time_to_live=0,
            message_title='New voicemail',
            message_body='From: 5555555555',
            badge=1,
            android_channel_id=DEFAULT_ANDROID_CHANNEL_ID,
        )

    @patch('wazo_webhookd.services.mobile.plugin.FCMNotificationLegacy')
    def test_send_chat_received(self, FCMNotificationLegacy):
        push_service = FCMNotificationLegacy.return_value

        data = {
            'alias': s.chat_alias,
            'content': s.chat_content,
            'notification_type': NotificationType.MESSAGE_RECEIVED,
            'items': '',
        }
        title = s.chat_alias
        body = s.chat_content

        self.push_notification._send_via_fcm(title, body, data, data_only=True)  # type: ignore

        assert push_service.FCM_END_POINT == FCMNotificationLegacy.FCM_END_POINT
        FCMNotificationLegacy.assert_called_once_with(api_key=s.fcm_api_key)
        push_service.single_device_data_message.assert_called_once_with(
            registration_id=s.token,
            data_message=data,
            time_to_live=0,
            low_priority=False,
            android_channel_id=DEFAULT_ANDROID_CHANNEL_ID,
        )

    @patch('wazo_webhookd.services.mobile.plugin.FCMNotificationLegacy')
    def test_send_notification_with_jwt(self, FCMNotificationLegacy):
        push_service = FCMNotificationLegacy.return_value
        task = Mock()
        config = {
            'mobile_fcm_notification_end_point': 'the url',
        }
        external_tokens = {'token': s.token}
        external_config: dict[str, str] = {}
        jwt = 'the jwt'
        push_notification = PushNotification(
            task,
            config,  # type: ignore
            external_tokens,  # type: ignore
            external_config,  # type: ignore
            jwt,
        )

        title = 'Incoming Call'  # Ignored
        body = 'From: 5555555555'  # Ignored
        data: NotificationPayload = {
            'notification_type': NotificationType.INCOMING_CALL,
            'items': '',
        }

        push_notification._send_via_fcm(title, body, data, data_only=False)

        assert push_service.FCM_END_POINT == 'the url'
        FCMNotificationLegacy.assert_called_once_with(api_key='the jwt')
        push_service.single_device_data_message.assert_not_called()
        push_service.notify_single_device.assert_called_once_with(
            low_priority=False,
            registration_id=s.token,
            data_message=data,
            time_to_live=0,
        )


class TestSendViaFCMv1(TestCase):
    def setUp(self):
        task = Mock()
        config = {
            'mobile_fcm_notification_end_point': 'the url',
        }
        external_tokens = {'token': s.token}
        external_config = {
            'fcm_service_account_info': s.fcm_service_account_info,
            'fcm_api_key': 'should be ignored',
        }
        jwt = Mock()

        self.push_notification = PushNotification(
            task,
            config,  # type: ignore
            external_tokens,  # type: ignore
            external_config,  # type: ignore
            jwt,
        )

    @patch('wazo_webhookd.services.mobile.plugin.json.loads')
    @patch('wazo_webhookd.services.mobile.plugin.FCMNotification')
    def test_send_incoming_call(self, FCMNotification, json_loads):
        push_service = FCMNotification.return_value

        title = 'Incoming Call'  # Ignored
        body = 'From: 5555555555'  # Ignored
        data: NotificationPayload = {
            'notification_type': NotificationType.INCOMING_CALL,
            'items': '',
        }

        self.push_notification._send_via_fcm(title, body, data, data_only=False)

        assert push_service.FCM_END_POINT == FCMNotification.FCM_END_POINT

        json_loads.assert_called_once_with(s.fcm_service_account_info)
        FCMNotification.assert_called_once_with(
            service_account_info=json_loads.return_value
        )
        push_service.single_device_data_message.assert_not_called()
        push_service.notify_single_device.assert_called_once_with(
            low_priority=False,
            registration_token=s.token,
            data_message=data,
            time_to_live=0,
        )

    @patch('wazo_webhookd.services.mobile.plugin.json.loads')
    @patch('wazo_webhookd.services.mobile.plugin.FCMNotification')
    def test_send_incoming_call_cancel(self, FCMNotification, json_loads):
        push_service = FCMNotification.return_value

        title = None  # Ignored
        body = None  # Ignored
        data: NotificationPayload = {
            'notification_type': NotificationType.CANCEL_INCOMING_CALL,
            'items': '',
        }

        self.push_notification._send_via_fcm(title, body, data, data_only=False)

        assert push_service.FCM_END_POINT == FCMNotification.FCM_END_POINT

        json_loads.assert_called_once_with(s.fcm_service_account_info)
        FCMNotification.assert_called_once_with(
            service_account_info=json_loads.return_value
        )
        push_service.single_device_data_message.assert_called_once_with(
            registration_token=s.token,
            data_message=data,
            time_to_live=0,
            android_channel_id=DEFAULT_ANDROID_CHANNEL_ID,
        )
        push_service.notify_single_device.assert_not_called()

    @patch('wazo_webhookd.services.mobile.plugin.json.loads')
    @patch('wazo_webhookd.services.mobile.plugin.FCMNotification')
    def test_send_voicemail_received(self, FCMNotification, json_loads):
        push_service = FCMNotification.return_value

        title = 'New voicemail'
        body = 'From: 5555555555'
        data: NotificationPayload = {
            'notification_type': NotificationType.VOICEMAIL_RECEIVED,
            'items': '',
        }

        self.push_notification._send_via_fcm(title, body, data, data_only=False)

        assert push_service.FCM_END_POINT == FCMNotification.FCM_END_POINT

        json_loads.assert_called_once_with(s.fcm_service_account_info)
        FCMNotification.assert_called_once_with(
            service_account_info=json_loads.return_value
        )
        push_service.single_device_data_message.assert_not_called()
        push_service.notify_single_device.assert_called_once_with(
            registration_token=s.token,
            data_message=data,
            time_to_live=0,
            message_title='New voicemail',
            message_body='From: 5555555555',
            badge=1,
            android_channel_id=DEFAULT_ANDROID_CHANNEL_ID,
        )

    @patch('wazo_webhookd.services.mobile.plugin.json.loads')
    @patch('wazo_webhookd.services.mobile.plugin.FCMNotification')
    def test_send_chat_received(self, FCMNotification, json_loads):
        push_service = FCMNotification.return_value

        data = {
            'alias': s.chat_alias,
            'content': s.chat_content,
            'notification_type': NotificationType.MESSAGE_RECEIVED,
            'items': '',
        }
        title = s.chat_alias
        body = s.chat_content

        self.push_notification._send_via_fcm(title, body, data, data_only=True)  # type: ignore

        assert push_service.FCM_END_POINT == FCMNotification.FCM_END_POINT

        json_loads.assert_called_once_with(s.fcm_service_account_info)
        FCMNotification.assert_called_once_with(
            service_account_info=json_loads.return_value
        )
        push_service.single_device_data_message.assert_called_once_with(
            registration_token=s.token,
            data_message=data,
            time_to_live=0,
            android_channel_id=DEFAULT_ANDROID_CHANNEL_ID,
            low_priority=False,
        )
