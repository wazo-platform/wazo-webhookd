# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import uuid
from flask import request
from wazo_webhookd.core.rest_api import AuthResource
from xivo.auth_verifier import required_acl

from .schema import SubscriptionSchema


class SubscriptionsResource(AuthResource):

    def __init__(self, service):
        self._service = service

    @required_acl('webhookd.subscriptions.read')
    def get(self):
        subscriptions = list(self._service.list())
        return {'items': SubscriptionSchema().dump(subscriptions, many=True).data,
                'total': len(subscriptions)}

    @required_acl('webhookd.subscriptions.create')
    def post(self):
        subscription = request.json
        subscription['uuid'] = str(uuid.uuid4())
        self._service.create(subscription)
        return subscription, 201


class SubscriptionResource(AuthResource):

    def __init__(self, service):
        self._service = service

    @required_acl('webhookd.subscriptions.{subscription_id}.read')
    def get(self, subscription_id):
        subscription = self._service.get(subscription_id)
        return SubscriptionSchema().dump(subscription).data

    @required_acl('webhookd.subscriptions.{subscription_id}.delete')
    def delete(self, subscription_id):
        self._service.delete(subscription_id)
        return '', 204
