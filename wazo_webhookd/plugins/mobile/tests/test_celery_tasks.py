# Copyright 2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from unittest.mock import patch, Mock, sentinel, call

from ..celery_tasks import send_notification, get_service_class
from ....services.mobile.plugin import PushNotification, Service as NotificationService


def test_get_service_class() -> None:
    assert get_service_class('Service') is NotificationService
    assert get_service_class('PushNotification') is PushNotification


@patch('wazo_webhookd.plugins.mobile.celery_tasks.get_service_class')
def test_send_notification(mock_get_service_class: Mock) -> None:
    service_mock = Mock()
    service_mock.get_external_data.return_value = (
        sentinel.external_tokens,
        sentinel.external_config,
        sentinel.jwt,
    )
    push_notification_mock = Mock()
    push_notification_mock()._send_notification.return_value = {'success': 1}
    service_classes = {
        'Service': service_mock,
        'PushNotification': push_notification_mock,
    }
    mock_get_service_class.side_effect = lambda name: service_classes[name]

    notification_payload = {
        'user_uuid': sentinel.user_uuid,
        'notification_type': sentinel.notification_type,
        'title': sentinel.title,
        'body': sentinel.body,
        'extra': sentinel.extra,
    }
    assert send_notification(sentinel.config, notification_payload) is True
    service_mock.get_external_data.assert_called_once_with(
        sentinel.config, sentinel.user_uuid
    )
    mock_get_service_class.assert_has_calls([call('Service'), call('PushNotification')])
    push_notification_mock.assert_called()
    push_notification_mock()._send_notification.assert_called_once_with(
        sentinel.notification_type,
        sentinel.title,
        sentinel.body,
        sentinel.extra,
    )
