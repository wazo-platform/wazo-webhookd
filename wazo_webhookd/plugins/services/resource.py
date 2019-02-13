# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_webhookd.rest_api import AuthResource
from xivo.auth_verifier import required_acl


class ServicesResource(AuthResource):

    def __init__(self, service_manager):
        self._service_manager = service_manager

    @required_acl('webhookd.subscriptions.services.read')
    def get(self):
        result = {
            'services': {name: {} for name in self._service_manager.names()},
        }
        return result, 200
