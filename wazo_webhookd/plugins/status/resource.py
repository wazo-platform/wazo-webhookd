# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_webhookd.rest_api import AuthResource
from xivo.auth_verifier import required_acl


class StatusResource(AuthResource):

    def __init__(self, bus_consumer):
        self._bus_consumer = bus_consumer

    @required_acl('webhookd.status.read')
    def get(self):
        result = {
            'bus_consumer': {
                'status': 'ok' if self._bus_consumer.is_running() else 'fail',
            }
        }
        return result, 200
