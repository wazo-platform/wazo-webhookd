# Copyright 2022-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from unittest import TestCase
from unittest.mock import patch, Mock, sentinel as s

from ..plugin import (
    DEFAULT_ANDROID_CHANNEL_ID,
    NotificationType,
    PushNotification,
    NotificationPayload,
)


class TestSendViaFcm(TestCase):
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

    @patch('wazo_webhookd.services.mobile.plugin.FCMNotification')
    def test_send_incoming_call(self, FCMNotification):
        push_service = FCMNotification.return_value

        title = 'Incoming Call'  # Ignored
        body = 'From: 5555555555'  # Ignored
        data: NotificationPayload = {
            'notification_type': NotificationType.INCOMING_CALL,
            'items': {},
        }

        self.push_notification._send_via_fcm(title, body, data)

        assert push_service.FCM_END_POINT == FCMNotification.FCM_END_POINT
        FCMNotification.assert_called_once_with(api_key=s.fcm_api_key)
        push_service.single_device_data_message.assert_not_called()
        push_service.notify_single_device.assert_called_once_with(
            registration_id=s.token,
            data_message=data,
            time_to_live=0,
            extra_notification_kwargs={'priority': 'high'},
        )

    @patch('wazo_webhookd.services.mobile.plugin.FCMNotification')
    def test_send_incoming_call_cancel(self, FCMNotification):
        push_service = FCMNotification.return_value

        title = None  # Ignored
        body = None  # Ignored
        data: NotificationPayload = {
            'notification_type': NotificationType.CANCEL_INCOMING_CALL,
            'items': {},
        }

        self.push_notification._send_via_fcm(title, body, data)

        assert push_service.FCM_END_POINT == FCMNotification.FCM_END_POINT
        FCMNotification.assert_called_once_with(api_key=s.fcm_api_key)
        push_service.single_device_data_message.assert_called_once_with(
            registration_id=s.token,
            data_message=data,
            time_to_live=0,
            extra_notification_kwargs={
                'android_channel_id': DEFAULT_ANDROID_CHANNEL_ID
            },
        )
        push_service.notify_single_device.assert_not_called()

    @patch('wazo_webhookd.services.mobile.plugin.FCMNotification')
    def test_send_voicemail_received(self, FCMNotification):
        push_service = FCMNotification.return_value

        title = 'New voicemail'
        body = 'From: 5555555555'
        data: NotificationPayload = {
            'notification_type': NotificationType.VOICEMAIL_RECEIVED,
            'items': {},
        }

        self.push_notification._send_via_fcm(title, body, data)

        assert push_service.FCM_END_POINT == FCMNotification.FCM_END_POINT
        FCMNotification.assert_called_once_with(api_key=s.fcm_api_key)
        push_service.single_device_data_message.assert_not_called()
        push_service.notify_single_device.assert_called_once_with(
            registration_id=s.token,
            data_message=data,
            time_to_live=0,
            message_title='New voicemail',
            message_body='From: 5555555555',
            badge=1,
            extra_notification_kwargs={
                'android_channel_id': DEFAULT_ANDROID_CHANNEL_ID
            },
        )

    @patch('wazo_webhookd.services.mobile.plugin.FCMNotification')
    def test_send_chat_received(self, FCMNotification):
        push_service = FCMNotification.return_value

        data = {
            'alias': s.chat_alias,
            'content': s.chat_content,
            'notification_type': NotificationType.MESSAGE_RECEIVED,
            'items': {},
        }
        title = s.chat_alias
        body = s.chat_content

        self.push_notification._send_via_fcm(title, body, data)  # type: ignore

        assert push_service.FCM_END_POINT == FCMNotification.FCM_END_POINT
        FCMNotification.assert_called_once_with(api_key=s.fcm_api_key)
        push_service.single_device_data_message.assert_not_called()
        push_service.notify_single_device.assert_called_once_with(
            registration_id=s.token,
            data_message=data,
            time_to_live=0,
            message_title=s.chat_alias,
            message_body=s.chat_content,
            badge=1,
            extra_notification_kwargs={
                'android_channel_id': DEFAULT_ANDROID_CHANNEL_ID
            },
        )

    @patch('wazo_webhookd.services.mobile.plugin.FCMNotification')
    def test_send_notification_with_jwt(self, FCMNotification):
        push_service = FCMNotification.return_value
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
            'items': {},
        }

        push_notification._send_via_fcm(title, body, data)

        assert push_service.FCM_END_POINT == 'the url'
        FCMNotification.assert_called_once_with(api_key='the jwt')
        push_service.single_device_data_message.assert_not_called()
        push_service.notify_single_device.assert_called_once_with(
            registration_id=s.token,
            data_message=data,
            time_to_live=0,
            extra_notification_kwargs={'priority': 'high'},
        )
