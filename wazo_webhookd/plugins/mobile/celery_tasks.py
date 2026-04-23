# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import requests
from celery import Task

from wazo_webhookd.celery import app

from ...services.mobile.plugin import PushNotification
from ...services.mobile.plugin import Service as PushNotificationService
from .schema import NotificationDict

if TYPE_CHECKING:
    from ...types import WebhookdConfigDict


MOBILE_SERVICE_ENTRYPOINT = 'mobile = wazo_webhookd.services.mobile.plugin'

logger = logging.getLogger(__name__)


@app.task(bind=True)
def send_notification(
    task: Task,
    config: WebhookdConfigDict,
    notification: NotificationDict,
) -> bool:
    push_trace_uuid = notification.get('extra', {}).get('items', {}).get(
        'push_trace_uuid'
    )
    logger.debug(
        "Attempting to send notification with payload: %s (attempt %d, push_trace_uuid=%s)",
        notification,
        task.request.retries + 1,
        push_trace_uuid,
    )
    try:
        (
            external_tokens,
            external_config,
            jwt,
        ) = PushNotificationService.get_external_data(config, notification['user_uuid'])
    except requests.HTTPError as e:
        if e.response and e.response.status_code == 404:
            logger.error(
                'Cannot send notification as no authentication exists for mobile (%s)',
                str(e),
            )
            return False
        raise

    push_notification = PushNotification(
        task,
        config,
        external_tokens,
        external_config,
        jwt,
    )
    response = push_notification.send_notification(
        notification['notification_type'],
        notification['title'],
        notification['body'],
        notification['extra'],
    )
    logger.debug('Push response: %s', response)
    return response['success']
