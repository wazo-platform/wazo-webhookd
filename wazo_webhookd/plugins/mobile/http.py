# Copyright 2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import logging
from typing import TypedDict, Literal

import requests
from flask import request
from wazo_auth_client.client import AuthClient
from xivo.rest_api_helpers import APIException
from xivo.tenant_flask_helpers import Tenant

from wazo_webhookd.rest_api import AuthResource
from xivo.auth_verifier import required_acl

from .schema import notification_schema
from .celery_tasks import send_notification
from ...auth import get_auth_token_from_request
from ...types import WebhookdConfigDict

logger = logging.getLogger(__name__)


class UserDict(TypedDict):
    """Only a subset of what is returned."""

    uuid: str
    tenant_uuid: str
    username: str
    enabled: bool
    purpose: Literal['external_api', 'internal']


class NotificationResource(AuthResource):
    def __init__(self, config: WebhookdConfigDict) -> None:
        self.config = config

    def verify_user_uuid(self, user_uuid: str) -> None:
        auth_client = AuthClient(**self.config['auth'])
        auth_client.tenant_uuid = Tenant.autodetect().uuid
        auth_client.set_token(get_auth_token_from_request())
        try:
            user: UserDict = auth_client.users.get(user_uuid)
            if user['enabled'] is not True:
                raise ValueError(f'User {user_uuid} is disabled')
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
