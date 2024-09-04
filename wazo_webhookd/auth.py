# Copyright 2017-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

from flask import request
from requests import HTTPError
from werkzeug.local import LocalProxy as Proxy
from xivo.auth_verifier import AuthServerUnreachable, required_tenant
from xivo.rest_api_helpers import APIException

from .exceptions import TokenWithUserUUIDRequiredError
from .rest_api import app

if TYPE_CHECKING:
    from wazo_auth_client.client import AuthClient
    from wazo_auth_client.types import TokenDict

logger = logging.getLogger(__name__)


class MasterTenantNotInitializedException(APIException):
    def __init__(self):
        msg = 'wazo-webhookd master tenant is not initialized'
        super().__init__(503, msg, 'master-tenant-not-initialized')


def get_auth_token_from_request() -> str | None:
    return request.headers.get('X-Auth-Token') or request.args.get('token')


class Token:
    def __init__(self, auth_client: AuthClient, token_id: str | None) -> None:
        try:
            self._token_info: TokenDict = auth_client.token.get(token_id)
        except HTTPError as e:
            logger.warning('HTTP error from wazo-auth while getting token: %s', e)
            raise AuthServerUnreachable(auth_client.host, auth_client.port, e)

    @property
    def user_uuid(self) -> str:
        if user_uuid := self._token_info['metadata']['uuid']:
            return user_uuid
        raise TokenWithUserUUIDRequiredError()

    @property
    def wazo_uuid(self) -> str:
        return self._token_info['xivo_uuid']

    @classmethod
    def from_request(cls, auth_client: AuthClient) -> Token:
        return cls(auth_client, get_auth_token_from_request())


def get_token_user_uuid_from_request(auth_client: AuthClient) -> str:
    token = request.headers.get('X-Auth-Token') or request.args.get('token')
    try:
        token_info: TokenDict = auth_client.token.get(token)
    except HTTPError as e:
        logger.warning('HTTP error from wazo-auth while getting token: %s', e)
        raise TokenWithUserUUIDRequiredError()

    if user_uuid := token_info['metadata']['uuid']:
        return user_uuid
    raise TokenWithUserUUIDRequiredError()


F = TypeVar('F')


def required_master_tenant() -> Callable[[F], F]:
    return required_tenant(master_tenant_uuid)


def init_master_tenant(token: TokenDict) -> None:
    tenant_uuid = token['metadata']['tenant_uuid']
    app.config['auth']['master_tenant_uuid'] = tenant_uuid


def get_master_tenant_uuid() -> str:
    if not app:
        raise Exception('Flask application not configured')

    if tenant_uuid := app.config['auth'].get('master_tenant_uuid'):
        return tenant_uuid
    raise MasterTenantNotInitializedException()


master_tenant_uuid = Proxy(get_master_tenant_uuid)
