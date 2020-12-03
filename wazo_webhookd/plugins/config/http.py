# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_webhookd.rest_api import AuthResource
from xivo.auth_verifier import required_acl


class ConfigResource(AuthResource):
    def __init__(self, config):
        self._config = config

    @required_acl('webhookd.config.read')
    def get(self):
        return dict(self._config), 200


class ConfigDebugResource(AuthResource):
    def __init__(self, service):
        self._service = service

    @required_acl('webhookd.config.debug.get')
    def get(self):
        debug_status = self._service.get_runtime_debug()
        response = {'debug-runtime': debug_status}
        return response, 200

    @required_acl('webhookd.config.debug.create')
    def post(self):
        self._service.enable_runtime_debug()
        return '', 204

    @required_acl('webhookd.config.debug.delete')
    def delete(self):
        self._service.disable_runtime_debug()
        return '', 204
