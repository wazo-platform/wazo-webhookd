# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from flask import request
from wazo_webhookd.rest_api import AuthResource
from xivo.auth_verifier import required_acl

from .schemas import config_schema


class ConfigResource(AuthResource):
    def __init__(self, config_service):
        self._config_service = config_service

    @required_acl('webhookd.config.read')
    def get(self):
        return self._config_service.get_config(), 200

    @required_acl('webhookd.config.update')
    def put(self):
        config = config_schema.load(request.get_json())
        return self._config_service.update_config(config)
