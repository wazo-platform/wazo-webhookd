# Copyright 2017-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import logging

from flask import request
from wazo_webhookd.rest_api import AuthResource
from xivo.auth_verifier import required_acl
from xivo.tenant_flask_helpers import token, Tenant

from .schema import (
    subscription_schema,
    subscription_list_params_schema,
    user_subscription_schema,
    subscription_log_schema,
    SubscriptionLogRequestSchema,
)

logger = logging.getLogger(__name__)


class SubscriptionsAuthResource(AuthResource):
    def __init__(self, service):
        super().__init__()
        self._service = service

    def visible_tenants(self, recurse: bool = True) -> list[str]:
        tenant_uuid = Tenant.autodetect().uuid
        if recurse:
            return [tenant.uuid for tenant in token.visible_tenants(tenant_uuid)]
        return [tenant_uuid]


class SubscriptionsResource(SubscriptionsAuthResource):
    @required_acl('webhookd.subscriptions.read')
    def get(self):
        params = subscription_list_params_schema.load(request.args)
        subscriptions = list(
            self._service.list(
                owner_tenant_uuids=self.visible_tenants(params["recurse"]),
                search_metadata=params['search_metadata'],
            )
        )
        return {
            'items': subscription_schema.dump(subscriptions, many=True),
            'total': len(subscriptions),
        }

    @required_acl('webhookd.subscriptions.create')
    def post(self):
        subscription = subscription_schema.load(request.json)
        subscription['owner_tenant_uuid'] = Tenant.autodetect().uuid
        return subscription_schema.dump(self._service.create(subscription)), 201


class SubscriptionResource(SubscriptionsAuthResource):
    @required_acl('webhookd.subscriptions.{subscription_uuid}.read')
    def get(self, subscription_uuid):
        subscription = self._service.get(subscription_uuid, self.visible_tenants())
        return subscription_schema.dump(subscription)

    @required_acl('webhookd.subscriptions.{subscription_uuid}.update')
    def put(self, subscription_uuid):
        subscription = subscription_schema.load(request.json)
        subscription['owner_tenant_uuid'] = Tenant.autodetect().uuid
        subscription = self._service.update(
            subscription_uuid, subscription, self.visible_tenants()
        )
        return subscription_schema.dump(subscription)

    @required_acl('webhookd.subscriptions.{subscription_uuid}.delete')
    def delete(self, subscription_uuid):
        self._service.delete(subscription_uuid, self.visible_tenants())
        return '', 204


class UserSubscriptionsResource(SubscriptionsAuthResource):
    @required_acl('webhookd.users.me.subscriptions.read')
    def get(self):
        params = subscription_list_params_schema.load(request.args)
        subscriptions = list(
            self._service.list(
                owner_user_uuid=token.user_uuid,
                owner_tenant_uuids=[token.tenant_uuid],
                search_metadata=params['search_metadata'],
            )
        )
        return {
            'items': subscription_schema.dump(subscriptions, many=True),
            'total': len(subscriptions),
        }

    @required_acl('webhookd.users.me.subscriptions.create')
    def post(self):
        subscription = user_subscription_schema.load(request.json)
        subscription['owner_tenant_uuid'] = token.tenant_uuid
        subscription['events_user_uuid'] = subscription[
            'owner_user_uuid'
        ] = token.user_uuid
        subscription['events_wazo_uuid'] = token.infos['xivo_uuid']
        return subscription_schema.dump(self._service.create(subscription)), 201


class UserSubscriptionResource(SubscriptionsAuthResource):
    @required_acl('webhookd.users.me.subscriptions.{subscription_uuid}.read')
    def get(self, subscription_uuid):
        subscription = self._service.get(
            subscription_uuid,
            owner_tenant_uuids=[token.tenant_uuid],
            owner_user_uuid=token.user_uuid,
        )
        return subscription_schema.dump(subscription)

    @required_acl('webhookd.users.me.subscriptions.{subscription_uuid}.update')
    def put(self, subscription_uuid):
        subscription = user_subscription_schema.load(request.json)
        subscription = self._service.update(
            subscription_uuid,
            subscription,
            owner_tenant_uuids=[token.tenant_uuid],
            owner_user_uuid=token.user_uuid,
        )
        return subscription_schema.dump(subscription)

    @required_acl('webhookd.users.me.subscriptions.{subscription_uuid}.delete')
    def delete(self, subscription_uuid):
        self._service.delete(
            subscription_uuid,
            owner_tenant_uuids=[token.tenant_uuid],
            owner_user_uuid=token.user_uuid,
        )
        return '', 204


class SubscriptionLogsResource(SubscriptionsAuthResource):
    @required_acl('webhookd.subscriptions.{subscription_uuid}.logs.read')
    def get(self, subscription_uuid):
        # NOTE:(sileht): To return 404 if the subscription doesn't exists
        self._service.get(subscription_uuid, self.visible_tenants())

        filter_parameters = SubscriptionLogRequestSchema().load(request.args)
        results = self._service.get_logs(subscription_uuid, **filter_parameters)
        return {
            'items': subscription_log_schema.dump(results, many=True),
            'total': len(results),
        }
