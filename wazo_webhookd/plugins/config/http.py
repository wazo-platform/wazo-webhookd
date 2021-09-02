# Copyright 2017-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from flask import request
from wazo_webhookd.rest_api import AuthResource
from wazo_webhookd.auth import required_master_tenant
from xivo.auth_verifier import required_acl
from jsonpatch import JsonPatch

from .schemas import config_patch_schema


class ConfigResource(AuthResource):
    def __init__(self, config_service):
        self._config_service = config_service

    @required_master_tenant()
    @required_acl('webhookd.config.read')
    def get(self):
        return self._config_service.get_config(), 200

    @required_acl('webhookd.config.update')
    def patch(self):
        config_patch = config_patch_schema.load(request.get_json(), many=True)
        config = self._config_service.get_config()
        patched_config = JsonPatch(config_patch).apply(config)
        self._config_service.update_config(patched_config)
        return self._config_service.get_config(), 200
