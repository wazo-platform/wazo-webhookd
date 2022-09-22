# Copyright 2017-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_webhookd import auth
from wazo_webhookd.rest_api import AuthResource
from xivo.auth_verifier import required_acl


class StatusResource(AuthResource):
    def __init__(self, bus_consumer, config):
        self._bus_consumer = bus_consumer
        self._config = config

    @required_acl('webhookd.status.read')
    def get(self):
        try:
            auth.get_master_tenant_uuid()
        except auth.MasterTenantNotInitializedException:
            master_tenant_status = 'fail'
        else:
            master_tenant_status = 'ok'

        result = {
            'bus_consumer': {
                'status': 'ok' if self._bus_consumer.consumer_connected() else 'fail'
            },
            'master_tenant': {'status': master_tenant_status},
        }
        return result, 200
