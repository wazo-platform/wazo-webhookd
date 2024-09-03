# Copyright 2023-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from unittest.mock import Mock, patch, sentinel

from ..celery_tasks import send_notification


@patch('wazo_webhookd.plugins.mobile.celery_tasks.PushNotificationService')
@patch('wazo_webhookd.plugins.mobile.celery_tasks.PushNotification')
def test_send_notification(
    mock_push_notification_class: Mock, mock_service_class: Mock
) -> None:
    mock_service_class.get_external_data.return_value = (
        sentinel.external_tokens,
        sentinel.external_config,
        sentinel.jwt,
    )
    mock_push_notification_class().send_notification.return_value = {'success': True}

    notification_payload = {
        'user_uuid': sentinel.user_uuid,
        'notification_type': sentinel.notification_type,
        'title': sentinel.title,
        'body': sentinel.body,
        'extra': sentinel.extra,
    }
    assert send_notification(sentinel.config, notification_payload) is True
    mock_service_class.get_external_data.assert_called_once_with(
        sentinel.config, sentinel.user_uuid
    )
    mock_push_notification_class.assert_called()
    mock_push_notification_class().send_notification.assert_called_once_with(
        sentinel.notification_type,
        sentinel.title,
        sentinel.body,
        sentinel.extra,
    )
