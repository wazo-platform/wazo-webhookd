# Copyright 2022-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import json
from unittest import TestCase
from unittest.mock import Mock, patch
from unittest.mock import sentinel as s

from requests import PreparedRequest, Response
from requests.adapters import HTTPAdapter

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
            'items': {},
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
            'items': {},
        }

        self.push_notification._send_via_fcm(title, body, data, data_only=False)

        assert push_service.FCM_END_POINT == FCMNotificationLegacy.FCM_END_POINT
        FCMNotificationLegacy.assert_called_once_with(api_key=s.fcm_api_key)
        push_service.single_device_data_message.assert_called_once_with(
            registration_id=s.token,
            data_message=data,
            time_to_live=0,
            android_channel_id=DEFAULT_ANDROID_CHANNEL_ID,
            low_priority=False,
        )
        push_service.notify_single_device.assert_not_called()

    @patch('wazo_webhookd.services.mobile.plugin.FCMNotificationLegacy')
    def test_send_voicemail_received(self, FCMNotificationLegacy):
        push_service = FCMNotificationLegacy.return_value

        title = 'New voicemail'
        body = 'From: 5555555555'
        data: NotificationPayload = {
            'notification_type': NotificationType.VOICEMAIL_RECEIVED,
            'items': {},
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
            'items': {},
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
            'items': {},
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


FCM_PROXY_URL = 'https://fcm.proxy.example.com/fcm/send'


def _fcm_proxy_reply(
    adapter: HTTPAdapter, request: PreparedRequest, **kwargs
) -> Response:
    response = Response()
    response.status_code = 200
    response.headers['Content-Type'] = 'application/json'
    response._content = json.dumps({'message_id': 'the-message-id'}).encode()
    response.request = request
    response.url = request.url or ''
    return response


def _json_body(request: PreparedRequest) -> dict:
    assert request.body is not None
    return json.loads(request.body)


class TestSendViaFcmProxyRequest(TestCase):
    '''HTTP request sent by the legacy client to the push proxy (JWT mode)'''

    def setUp(self):
        self.push_notification = PushNotification(
            Mock(),
            {'mobile_fcm_notification_end_point': FCM_PROXY_URL},  # type: ignore
            {'token': 'device-token'},  # type: ignore
            {},  # type: ignore
            'the-jwt',
        )

    def _send(
        self,
        notification_type: str,
        data_only: bool,
        title: str | None = None,
        body: str | None = None,
    ) -> PreparedRequest:
        data: NotificationPayload = {
            'notification_type': notification_type,
            'items': {'some': 'item'},
        }
        with patch.object(
            HTTPAdapter, 'send', autospec=True, side_effect=_fcm_proxy_reply
        ) as send:
            self.push_notification._send_via_fcm(title, body, data, data_only)

        send.assert_called_once()
        _, request = send.call_args.args
        return request

    def test_request_is_sent_to_proxy_with_jwt(self):
        request = self._send(NotificationType.INCOMING_CALL, data_only=False)

        assert request.url == FCM_PROXY_URL
        assert request.headers['Authorization'] == 'key=the-jwt'

    def test_incoming_call_expires_immediately(self):
        request = self._send(NotificationType.INCOMING_CALL, data_only=False)

        assert _json_body(request).get('time_to_live') == 0

    def test_cancel_incoming_call_expires_immediately(self):
        request = self._send(NotificationType.CANCEL_INCOMING_CALL, data_only=True)

        assert _json_body(request).get('time_to_live') == 0

    def test_data_only_notification_expires_immediately(self):
        request = self._send(NotificationType.MISSED_CALL, data_only=True)

        assert _json_body(request).get('time_to_live') == 0

    def test_notification_message_expires_immediately(self):
        request = self._send(
            NotificationType.VOICEMAIL_RECEIVED,
            data_only=False,
            title='New voicemail',
            body='From: 5555555555',
        )

        assert _json_body(request).get('time_to_live') == 0


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
            'items': {},
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
            data_message={
                'notification_type': NotificationType.INCOMING_CALL,
                'items': '',
            },
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
            'items': {},
        }

        self.push_notification._send_via_fcm(title, body, data, data_only=False)

        assert push_service.FCM_END_POINT == FCMNotification.FCM_END_POINT

        json_loads.assert_called_once_with(s.fcm_service_account_info)
        FCMNotification.assert_called_once_with(
            service_account_info=json_loads.return_value
        )
        push_service.single_device_data_message.assert_called_once_with(
            registration_token=s.token,
            data_message={
                'notification_type': NotificationType.CANCEL_INCOMING_CALL,
                'items': '',
            },
            time_to_live=0,
            android_channel_id=DEFAULT_ANDROID_CHANNEL_ID,
            low_priority=False,
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
            'items': {},
        }

        self.push_notification._send_via_fcm(title, body, data, data_only=True)

        assert push_service.FCM_END_POINT == FCMNotification.FCM_END_POINT

        json_loads.assert_called_once_with(s.fcm_service_account_info)
        FCMNotification.assert_called_once_with(
            service_account_info=json_loads.return_value
        )
        push_service.single_device_data_message.assert_called_once_with(
            registration_token=s.token,
            data_message={
                'notification_type': NotificationType.VOICEMAIL_RECEIVED,
                'items': '',
            },
            time_to_live=0,
            android_channel_id=DEFAULT_ANDROID_CHANNEL_ID,
            low_priority=False,
        )

    @patch('wazo_webhookd.services.mobile.plugin.json.loads')
    @patch('wazo_webhookd.services.mobile.plugin.FCMNotification')
    def test_send_chat_received(self, FCMNotification, json_loads):
        push_service = FCMNotification.return_value

        data = {
            'alias': s.chat_alias,
            'content': s.chat_content,
            'notification_type': NotificationType.MESSAGE_RECEIVED,
            'items': {},
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
            data_message={
                'alias': s.chat_alias,
                'content': s.chat_content,
                'notification_type': NotificationType.MESSAGE_RECEIVED,
                'items': '',
            },
            time_to_live=0,
            android_channel_id=DEFAULT_ANDROID_CHANNEL_ID,
            low_priority=False,
        )
