# Copyright 2023-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from typing import Literal, TypedDict

import requests
from flask import request
from wazo_auth_client.client import AuthClient
from xivo.auth_verifier import required_acl
from xivo.rest_api_helpers import APIException
from xivo.tenant_flask_helpers import Tenant

from wazo_webhookd.rest_api import AuthResource

from ...types import WebhookdConfigDict
from .celery_tasks import send_notification
from .schema import notification_schema

logger = logging.getLogger(__name__)


class UserDict(TypedDict):
    """Only a subset of what is returned."""

    uuid: str
    tenant_uuid: str
    username: str
    enabled: bool
    purpose: Literal['external_api', 'internal']


class NotificationResource(AuthResource):
    def __init__(self, config: WebhookdConfigDict, auth_client: AuthClient) -> None:
        self.auth_client = auth_client
        self.config = config

    def verify_user_uuid(self, user_uuid: str) -> None:
        tenant_uuid = Tenant.autodetect().uuid
        try:
            user: UserDict = self.auth_client.users.get(user_uuid)
            if user['enabled'] is not True:
                raise ValueError(f'User {user_uuid} is disabled')
            if user['tenant_uuid'] != tenant_uuid:
                raise ValueError('Invalid tenant for specified `user_uuid`')
        except (requests.HTTPError, ValueError) as e:
            logger.debug('Error fetching user: %s', str(e))
            raise APIException(
                400, 'User UUID is invalid or unauthorized', 'invalid-user-uuid'
            )

    @required_acl('webhookd.mobile.notifications.send')
    def post(self) -> tuple[str, int]:
        notification = notification_schema.load(request.json)
        self.verify_user_uuid(notification['user_uuid'])
        result = send_notification.apply_async(
            args=(dict(self.config), notification),
            retry=True,
            retry_policy={
                'max_retries': self.config["hook_max_attempts"],
                # When we can finally use Celery 5.3 this would be good:
                # 'retry_errors': (requests.HTTPError,),
            },
        )
        logger.debug('Notification: %s, was sent (%s)', notification, result)
        return '', 204
