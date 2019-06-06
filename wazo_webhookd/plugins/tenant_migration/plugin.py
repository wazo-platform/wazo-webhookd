# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_auth_client import Client as AuthClient
from wazo_webhookd.rest_api import api

from . import (
    http,
    service,
)


# This plugin is used for the tenant uuid migration between wazo-auth and webhookd
class Plugin(object):

    def load(self, dependencies):
        config = dependencies['config']
        auth_client = AuthClient(**config['auth'])
        tenant_upgrade_service = service.WebhookTenantUpgradeService(config)
        api.add_resource(
            http.WebhookTenantUpgradeResource,
            '/tenant-migration',
            resource_class_args=[tenant_upgrade_service, auth_client],
        )
