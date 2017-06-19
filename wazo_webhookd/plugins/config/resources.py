# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from wazo_webhookd.core.rest_api import AuthResource
from xivo.auth_verifier import required_acl


class ConfigResource(AuthResource):

    api_path = '/config'

    def __init__(self, config):
        self._config = config

    @required_acl('plugind.config.read')
    def get(self):
        return dict(self._config), 200
