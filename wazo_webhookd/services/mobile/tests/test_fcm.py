# Copyright 2022-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from unittest import TestCase
from unittest.mock import patch, Mock, sentinel as s

from ..plugin import PushNotification


class TestSendViaFcm(TestCase):
    def setUp(self):
        task = Mock()
        config = {
            'mobile_fcm_notification_send_jwt_token': False,
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
        channel_id = 'wazo-notification-call'
        data = s.incoming_call_data

        self.push_notification._send_via_fcm(title, body, channel_id, data)

        push_service.single_device_data_message.assert_not_called()
        push_service.notify_single_device.assert_called_once_with(
            registration_id=s.token,
            data_message=s.incoming_call_data,
            extra_notification_kwargs={'priority': 'high'},
        )

    @patch('wazo_webhookd.services.mobile.plugin.FCMNotification')
    def test_send_incoming_call_cancel(self, FCMNotification):
        push_service = FCMNotification.return_value

        title = None  # Ignored
        body = None  # Ignored
        channel_id = 'wazo-notification-cancel-call'
        data = s.cancel_incoming_call_data

        self.push_notification._send_via_fcm(title, body, channel_id, data)

        push_service.single_device_data_message.assert_called_once_with(
            registration_id=s.token,
            data_message=s.cancel_incoming_call_data,
            extra_notification_kwargs={'android_channel_id': channel_id},
        )
        push_service.notify_single_device.assert_not_called()

    @patch('wazo_webhookd.services.mobile.plugin.FCMNotification')
    def test_send_voicemail_received(self, FCMNotification):
        push_service = FCMNotification.return_value

        title = 'New voicemail'
        body = 'From: 5555555555'
        channel_id = 'wazo-notification-voicemail'
        data = s.voicemail_data

        self.push_notification._send_via_fcm(title, body, channel_id, data)

        push_service.single_device_data_message.assert_not_called()
        push_service.notify_single_device.assert_called_once_with(
            registration_id=s.token,
            data_message=s.voicemail_data,
            message_title='New voicemail',
            message_body='From: 5555555555',
            badge=1,
            extra_notification_kwargs={'android_channel_id': channel_id},
        )

    @patch('wazo_webhookd.services.mobile.plugin.FCMNotification')
    def test_send_chat_received(self, FCMNotification):
        push_service = FCMNotification.return_value

        data = {
            'alias': s.chat_alias,
            'content': s.chat_content,
        }
        title = s.chat_alias
        body = s.chat_content
        channel_id = 'wazo-notification-chat'

        self.push_notification._send_via_fcm(title, body, channel_id, data)

        push_service.single_device_data_message.assert_not_called()
        push_service.notify_single_device.assert_called_once_with(
            registration_id=s.token,
            data_message=data,
            message_title=s.chat_alias,
            message_body=s.chat_content,
            badge=1,
            extra_notification_kwargs={'android_channel_id': channel_id},
        )
