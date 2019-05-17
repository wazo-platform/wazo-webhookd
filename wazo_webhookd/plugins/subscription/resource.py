# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import uuid

from flask import request
from wazo_webhookd.auth import get_token_user_uuid_from_request
from wazo_webhookd.rest_api import AuthResource
from xivo.auth_verifier import required_acl
from wazo_webhookd.auth import Token

from .schema import (
    subscription_schema,
    subscription_list_params_schema,
    user_subscription_schema,
)


class SubscriptionsResource(AuthResource):
    def __init__(self, service):
        self._service = service

    @required_acl("webhookd.subscriptions.read")
    def get(self):
        params = subscription_list_params_schema.load(request.args).data
        subscriptions = list(self._service.list(**params))
        return {
            "items": subscription_schema.dump(subscriptions, many=True).data,
            "total": len(subscriptions),
        }

    @required_acl("webhookd.subscriptions.create")
    def post(self):
        subscription = subscription_schema.load(request.json).data
        subscription["uuid"] = str(uuid.uuid4())
        self._service.create(subscription)
        return subscription, 201


class SubscriptionResource(AuthResource):
    def __init__(self, service):
        self._service = service

    @required_acl("webhookd.subscriptions.{subscription_uuid}.read")
    def get(self, subscription_uuid):
        subscription = self._service.get(subscription_uuid)
        return subscription_schema.dump(subscription).data

    @required_acl("webhookd.subscriptions.{subscription_uuid}.update")
    def put(self, subscription_uuid):
        subscription = subscription_schema.load(request.json).data
        subscription = self._service.update(subscription_uuid, subscription)
        return subscription_schema.dump(subscription).data

    @required_acl("webhookd.subscriptions.{subscription_uuid}.delete")
    def delete(self, subscription_uuid):
        self._service.delete(subscription_uuid)
        return "", 204


class UserSubscriptionsResource(AuthResource):
    def __init__(self, auth_client, service):
        self._auth_client = auth_client
        self._service = service

    @required_acl("webhookd.users.me.subscriptions.read")
    def get(self):
        user_uuid = get_token_user_uuid_from_request(self._auth_client)
        params = subscription_list_params_schema.load(request.args).data
        subscriptions = list(self._service.list(owner_user_uuid=user_uuid, **params))
        return {
            "items": subscription_schema.dump(subscriptions, many=True).data,
            "total": len(subscriptions),
        }

    @required_acl("webhookd.users.me.subscriptions.create")
    def post(self):
        subscription = user_subscription_schema.load(request.json).data
        token = Token.from_request(self._auth_client)
        subscription["events_user_uuid"] = subscription[
            "owner_user_uuid"
        ] = token.user_uuid()
        subscription["events_wazo_uuid"] = token.wazo_uuid()
        subscription["uuid"] = str(uuid.uuid4())
        self._service.create(subscription)
        return subscription, 201


class UserSubscriptionResource(AuthResource):
    def __init__(self, auth_client, service):
        self._auth_client = auth_client
        self._service = service

    @required_acl("webhookd.users.me.subscriptions.{subscription_uuid}.read")
    def get(self, subscription_uuid):
        user_uuid = get_token_user_uuid_from_request(self._auth_client)
        subscription = self._service.get_as_user(subscription_uuid, user_uuid)
        return subscription_schema.dump(subscription).data

    @required_acl("webhookd.users.me.subscriptions.{subscription_uuid}.update")
    def put(self, subscription_uuid):
        user_uuid = get_token_user_uuid_from_request(self._auth_client)
        subscription = user_subscription_schema.load(request.json).data
        subscription = self._service.update_as_user(
            subscription_uuid, subscription, user_uuid
        )
        return subscription_schema.dump(subscription).data

    @required_acl("webhookd.users.me.subscriptions.{subscription_uuid}.delete")
    def delete(self, subscription_uuid):
        user_uuid = get_token_user_uuid_from_request(self._auth_client)
        self._service.delete_as_user(subscription_uuid, user_uuid)
        return "", 204
