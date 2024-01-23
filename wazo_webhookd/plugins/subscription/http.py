# Copyright 2017-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, TypedDict

from flask import request
from xivo.auth_verifier import required_acl
from xivo.tenant_flask_helpers import Tenant, token

from wazo_webhookd.rest_api import AuthResource

from .schema import (
    SubscriptionDict,
    SubscriptionLogDict,
    SubscriptionLogRequestSchema,
    UserSubscriptionDict,
    subscription_list_params_schema,
    subscription_log_schema,
    subscription_schema,
    user_subscription_schema,
)

if TYPE_CHECKING:
    from .service import SubscriptionService


logger = logging.getLogger(__name__)


class SubscriptionListResponseDict(TypedDict):
    items: list[SubscriptionDict]
    total: int


class SubscriptionLogListResponseDict(TypedDict):
    items: list[SubscriptionLogDict]
    total: int


class UserSubscriptionListResponseDict(TypedDict):
    items: list[UserSubscriptionDict]
    total: int


class SubscriptionsAuthResource(AuthResource):
    def __init__(self, service: SubscriptionService) -> None:
        super().__init__()
        self._service = service

    def visible_tenants(self, recurse: bool = True) -> list[str]:
        tenant_uuid = Tenant.autodetect().uuid
        if recurse:
            return [tenant.uuid for tenant in token.visible_tenants(tenant_uuid)]
        return [tenant_uuid]


class SubscriptionsResource(SubscriptionsAuthResource):
    @required_acl('webhookd.subscriptions.read')
    def get(self) -> SubscriptionListResponseDict:
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
    def post(self) -> tuple[SubscriptionDict, int]:
        subscription = subscription_schema.load(request.json)
        subscription['owner_tenant_uuid'] = Tenant.autodetect().uuid
        return subscription_schema.dump(self._service.create(subscription)), 201


class SubscriptionResource(SubscriptionsAuthResource):
    @required_acl('webhookd.subscriptions.{subscription_uuid}.read')
    def get(self, subscription_uuid: str) -> SubscriptionDict:
        subscription = self._service.get(subscription_uuid, self.visible_tenants())
        return subscription_schema.dump(subscription)

    @required_acl('webhookd.subscriptions.{subscription_uuid}.update')
    def put(self, subscription_uuid: str) -> SubscriptionDict:
        subscription = subscription_schema.load(request.json)
        subscription['owner_tenant_uuid'] = Tenant.autodetect().uuid
        subscription = self._service.update(
            subscription_uuid, subscription, self.visible_tenants()
        )
        return subscription_schema.dump(subscription)

    @required_acl('webhookd.subscriptions.{subscription_uuid}.delete')
    def delete(self, subscription_uuid: str) -> tuple[str, int]:
        self._service.delete(subscription_uuid, self.visible_tenants())
        return '', 204


class UserSubscriptionsResource(SubscriptionsAuthResource):
    @required_acl('webhookd.users.me.subscriptions.read')
    def get(self) -> UserSubscriptionListResponseDict:
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
    def post(self) -> tuple[UserSubscriptionDict, int]:
        subscription = user_subscription_schema.load(request.json)
        subscription['owner_tenant_uuid'] = token.tenant_uuid
        subscription['events_user_uuid'] = subscription[
            'owner_user_uuid'
        ] = token.user_uuid
        subscription['events_wazo_uuid'] = token.infos['xivo_uuid']
        return subscription_schema.dump(self._service.create(subscription)), 201


class UserSubscriptionResource(SubscriptionsAuthResource):
    @required_acl('webhookd.users.me.subscriptions.{subscription_uuid}.read')
    def get(self, subscription_uuid: str) -> UserSubscriptionDict:
        subscription = self._service.get(
            subscription_uuid,
            owner_tenant_uuids=[token.tenant_uuid],
            owner_user_uuid=token.user_uuid,
        )
        return subscription_schema.dump(subscription)

    @required_acl('webhookd.users.me.subscriptions.{subscription_uuid}.update')
    def put(self, subscription_uuid: str) -> UserSubscriptionDict:
        subscription = user_subscription_schema.load(request.json)
        subscription = self._service.update(
            subscription_uuid,
            subscription,
            owner_tenant_uuids=[token.tenant_uuid],
            owner_user_uuid=token.user_uuid,
        )
        return subscription_schema.dump(subscription)

    @required_acl('webhookd.users.me.subscriptions.{subscription_uuid}.delete')
    def delete(self, subscription_uuid: str) -> tuple[str, int]:
        self._service.delete(
            subscription_uuid,
            owner_tenant_uuids=[token.tenant_uuid],
            owner_user_uuid=token.user_uuid,
        )
        return '', 204


class SubscriptionLogsResource(SubscriptionsAuthResource):
    @required_acl('webhookd.subscriptions.{subscription_uuid}.logs.read')
    def get(self, subscription_uuid: str) -> SubscriptionLogListResponseDict:
        # NOTE:(sileht): To return 404 if the subscription doesn't exist
        self._service.get(subscription_uuid, self.visible_tenants())

        filter_parameters = SubscriptionLogRequestSchema().load(request.args)
        results = self._service.get_logs(subscription_uuid, **filter_parameters)
        return {
            'items': subscription_log_schema.dump(results, many=True),
            'total': len(results),
        }
