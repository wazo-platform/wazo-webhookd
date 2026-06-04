# Copyright 2023-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from unittest.mock import Mock, patch, sentinel

import pytest
import requests
from celery.exceptions import Retry

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
def test_send_notification_retries_on_cached_auth_401(mock_service_class: Mock) -> None:
    mock_service_class.get_external_data.side_effect = _make_http_error(401)
    mock_service_class.is_cached_auth_401.return_value = True

    notification_payload = {
        'user_uuid': sentinel.user_uuid,
        'notification_type': sentinel.notification_type,
        'title': sentinel.title,
        'body': sentinel.body,
        'extra': sentinel.extra,
    }
    # When called directly (not via apply_async), Celery's task.retry()
    # re-raises the original exception rather than Retry; patch it so we can
    # assert that retry was requested.
    with patch.object(send_notification, 'retry', side_effect=Retry()) as mock_retry:
        with pytest.raises(Retry):
            send_notification(sentinel.config, notification_payload)
    mock_retry.assert_called_once()


@patch('wazo_webhookd.plugins.mobile.celery_tasks.PushNotificationService')
def test_send_notification_propagates_non_cached_auth_errors(
    mock_service_class: Mock,
) -> None:
    mock_service_class.get_external_data.side_effect = _make_http_error(500)
    mock_service_class.is_cached_auth_401.return_value = False

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
    # 404 takes precedence; is_cached_auth_401 must not be consulted
    mock_service_class.is_cached_auth_401.assert_not_called()
