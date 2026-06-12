# Copyright 2023-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from unittest.mock import Mock, patch, sentinel

import pytest
import requests

from ..celery_tasks import send_notification


def _make_http_error(status_code, url='https://localhost:9497/0.1/users/x'):
    response = requests.Response()
    response.status_code = status_code
    response.url = url
    return requests.HTTPError(response=response)


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


@patch('wazo_webhookd.plugins.mobile.celery_tasks.PushNotificationService')
def test_send_notification_propagates_http_errors(mock_service_class: Mock) -> None:
    mock_service_class.get_external_data.side_effect = _make_http_error(500)

    notification_payload = {
        'user_uuid': sentinel.user_uuid,
        'notification_type': sentinel.notification_type,
        'title': sentinel.title,
        'body': sentinel.body,
        'extra': sentinel.extra,
    }
    with pytest.raises(requests.HTTPError):
        send_notification(sentinel.config, notification_payload)


@patch('wazo_webhookd.plugins.mobile.celery_tasks.PushNotificationService')
def test_send_notification_returns_false_on_404(mock_service_class: Mock) -> None:
    mock_service_class.get_external_data.side_effect = _make_http_error(404)

    notification_payload = {
        'user_uuid': sentinel.user_uuid,
        'notification_type': sentinel.notification_type,
        'title': sentinel.title,
        'body': sentinel.body,
        'extra': sentinel.extra,
    }
    assert send_notification(sentinel.config, notification_payload) is False
