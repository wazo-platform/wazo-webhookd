# Copyright 2019-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal, overload

import requests
from celery import Task
from pkg_resources import EntryPoint

from wazo_webhookd.celery import app
from .schema import NotificationDict

if TYPE_CHECKING:
    from ...services.mobile.plugin import (
        PushNotification,
        Service as PushNotificationService,
    )
    from ...types import WebhookdConfigDict


MOBILE_SERVICE_ENTRYPOINT = 'mobile = wazo_webhookd.services.mobile.plugin'

logger = logging.getLogger(__name__)

if TYPE_CHECKING:

    @overload
    def get_service_class(name: Literal['Service']) -> type[PushNotificationService]:
        ...

    @overload
    def get_service_class(name: Literal['PushNotification']) -> type[PushNotification]:
        ...


def get_service_class(name: str) -> type[PushNotificationService | PushNotification]:
    return EntryPoint.parse(f'{MOBILE_SERVICE_ENTRYPOINT}:{name}').resolve()


@app.task(bind=True)
def send_notification(
    task: Task,
    config: WebhookdConfigDict,
    notification: NotificationDict,
) -> bool:
    service_class: type[PushNotificationService] = get_service_class('Service')
    notification_class: type[PushNotification] = get_service_class('PushNotification')

    logger.debug(
        "Attempting to send notification with payload: %s (attempt %d)",
        notification,
        task.request.retries + 1,
    )
    try:
        external_tokens, external_config, jwt = service_class.get_external_data(
            config, notification['user_uuid']
        )
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            logger.error(
                'Cannot send notification as no authentication exists for mobile (%s)',
                str(e),
            )
            return False
        raise

    push_notification = notification_class(
        task,
        config,
        external_tokens,
        external_config,
        jwt,
    )
    response = push_notification._send_notification(
        notification['notification_type'],
        notification['title'],
        notification['body'],
        notification['extra'],
    )
    logger.debug('Push response: %s', response)
    if 'success' in response:
        return response['success'] == 1  # type: ignore[typeddict-item]
    return not response.get('error')
