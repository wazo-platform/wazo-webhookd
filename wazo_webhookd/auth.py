# Copyright 2017-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from flask import request
from requests import HTTPError
from xivo.auth_verifier import AuthServerUnreachable, required_tenant
from xivo.rest_api_helpers import APIException

from werkzeug.local import LocalProxy as Proxy
from .rest_api import app
from .exceptions import TokenWithUserUUIDRequiredError

logger = logging.getLogger(__name__)




class _DeferredLoader:
    def __init__(self):
        self._post_hooks = []

    @property
    def _has_master_tenant(self):
        try:
            get_master_tenant_uuid()
        except MasterTenantNotInitializedException:
            return False
        else:
            return True

    def execute_after_master_tenant(self, func, *args, **kwargs):
        callback = (func, args, kwargs,)
        if self._has_master_tenant:
            self._execute_callback(callback)
        self._post_hooks.append(callback)

    def run_post_hooks(self):
        for callback in self._post_hooks:
            self._execute_callback(callback)

    def _execute_callback(self, callback):
        callback, args, kwargs = callback
        try:
            callback(*args, **kwargs)
        except Exception:
            logger.error('error during callback execution')
            raise


deferred_loader = _DeferredLoader()


def get_token_user_uuid_from_request(auth_client):
    token = request.headers.get('X-Auth-Token') or request.args.get('token')
    try:
        token_infos = auth_client.token.get(token)
    except HTTPError as e:
        logger.warning('HTTP error from wazo-auth while getting token: %s', e)
        raise TokenWithUserUUIDRequiredError()
    user_uuid = token_infos['metadata']['uuid']
    if not user_uuid:
        raise TokenWithUserUUIDRequiredError()
    return user_uuid


class MasterTenantNotInitializedException(APIException):
    def __init__(self):
        msg = 'wazo-webhookd master tenant is not initialized'
        super().__init__(503, msg, 'master-tenant-not-initialized')


def required_master_tenant():
    return required_tenant(master_tenant_uuid)


def init_master_tenant(token):
    tenant_uuid = token['metadata']['tenant_uuid']
    app.config['auth']['master_tenant_uuid'] = tenant_uuid
    deferred_loader.run_post_hooks()


def get_master_tenant_uuid():
    if not app:
        raise Exception('Flask application not configured')

    tenant_uuid = app.config['auth'].get('master_tenant_uuid')
    if not tenant_uuid:
        raise MasterTenantNotInitializedException()
    return tenant_uuid


master_tenant_uuid = Proxy(get_master_tenant_uuid)


class Token:
    def __init__(self, auth_client, token_id):
        try:
            self._token_infos = auth_client.token.get(token_id)
        except HTTPError as e:
            logger.warning('HTTP error from wazo-auth while getting token: %s', e)
            raise AuthServerUnreachable(auth_client.host, auth_client.port, e)

    def user_uuid(self):
        user_uuid = self._token_infos['metadata']['uuid']
        if not user_uuid:
            raise TokenWithUserUUIDRequiredError()
        return user_uuid

    def wazo_uuid(self):
        return self._token_infos['xivo_uuid']

    @classmethod
    def from_request(cls, auth_client):
        token_id = request.headers.get('X-Auth-Token') or request.args.get('token')
        return cls(auth_client, token_id)
