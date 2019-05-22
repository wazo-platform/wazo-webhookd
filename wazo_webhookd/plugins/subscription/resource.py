# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import uuid

from flask import request
from wazo_webhookd.rest_api import AuthResource
from xivo.auth_verifier import required_acl
from xivo.tenant_flask_helpers import (
    auth_client,
    token,
    Tenant,
)
from xivo import tenant_helpers

from .schema import (
    subscription_schema,
    subscription_list_params_schema,
    user_subscription_schema,
)

logger = logging.getLogger(__name__)


class SubscriptionsAuthResource(AuthResource):
    def __init__(self, service):
        super().__init__()
        self._service = service

    def visible_tenants(self, recurse=True):
        tenant_uuid = Tenant.autodetect().uuid
        if recurse:
            return [tenant.uuid for tenant in tenant_helpers.visible_tenants(auth_client, tenant_uuid)]
        else:
            return [tenant_uuid]


class SubscriptionsResource(SubscriptionsAuthResource):

    @required_acl('webhookd.subscriptions.read')
    def get(self):
        params = subscription_list_params_schema.load(request.args).data
        subscriptions = list(self._service.list(
            owner_tenant_uuids=self.visible_tenants(params["recurse"]),
            search_metadata=params['search_metadata']
        ))
        return {'items': subscription_schema.dump(subscriptions, many=True).data,
                'total': len(subscriptions)}

    @required_acl('webhookd.subscriptions.create')
    def post(self):
        subscription = subscription_schema.load(request.json).data
        subscription['uuid'] = str(uuid.uuid4())
        subscription['owner_tenant_uuid'] = Tenant.autodetect().uuid
        self._service.create(subscription)
        return subscription, 201


class SubscriptionResource(SubscriptionsAuthResource):

    @required_acl('webhookd.subscriptions.{subscription_uuid}.read')
    def get(self, subscription_uuid):
        subscription = self._service.get(subscription_uuid,
                                         self.visible_tenants())
        return subscription_schema.dump(subscription).data

    @required_acl('webhookd.subscriptions.{subscription_uuid}.update')
    def put(self, subscription_uuid):
        subscription = subscription_schema.load(request.json).data
        subscription['owner_tenant_uuid'] = Tenant.autodetect().uuid
        subscription = self._service.update(subscription_uuid,
                                            subscription,
                                            self.visible_tenants())
        return subscription_schema.dump(subscription).data

    @required_acl('webhookd.subscriptions.{subscription_uuid}.delete')
    def delete(self, subscription_uuid):
        self._service.delete(subscription_uuid, self.visible_tenants())
        return '', 204


class UserSubscriptionsResource(SubscriptionsAuthResource):

    @required_acl('webhookd.users.me.subscriptions.read')
    def get(self):
        params = subscription_list_params_schema.load(request.args).data
        subscriptions = list(self._service.list(
            owner_user_uuid=token.user_uuid,
            owner_tenant_uuids=[token.tenant_uuid],
            search_metadata=params['search_metadata']
        ))
        return {'items': subscription_schema.dump(subscriptions, many=True).data,
                'total': len(subscriptions)}

    @required_acl('webhookd.users.me.subscriptions.create')
    def post(self):
        subscription = user_subscription_schema.load(request.json).data
        subscription['owner_tenant_uuid'] = token.tenant_uuid
        subscription['events_user_uuid'] = subscription['owner_user_uuid'] = token.user_uuid
        subscription['events_wazo_uuid'] = token.infos['xivo_uuid']
        subscription['uuid'] = str(uuid.uuid4())
        self._service.create(subscription)
        return subscription, 201


class UserSubscriptionResource(SubscriptionsAuthResource):

    @required_acl('webhookd.users.me.subscriptions.{subscription_uuid}.read')
    def get(self, subscription_uuid):
        subscription = self._service.get(subscription_uuid,
                                         owner_tenant_uuids=[token.tenant_uuid],
                                         owner_user_uuid=token.user_uuid)
        return subscription_schema.dump(subscription).data

    @required_acl('webhookd.users.me.subscriptions.{subscription_uuid}.update')
    def put(self, subscription_uuid):
        subscription = user_subscription_schema.load(request.json).data
        subscription = self._service.update(subscription_uuid,
                                            subscription,
                                            owner_tenant_uuids=[token.tenant_uuid],
                                            owner_user_uuid=token.user_uuid)
        return subscription_schema.dump(subscription).data

    @required_acl('webhookd.users.me.subscriptions.{subscription_uuid}.delete')
    def delete(self, subscription_uuid):
        self._service.delete(subscription_uuid,
                             owner_tenant_uuids=[token.tenant_uuid],
                             owner_user_uuid=token.user_uuid)
        return '', 204
