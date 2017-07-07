# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import uuid
from flask import request
from wazo_webhookd.core.rest_api import AuthResource
from xivo.auth_verifier import required_acl


class SubscriptionsResource(AuthResource):

    @required_acl('webhookd.subscriptions.create')
    def post(self):
        subscription = request.json
        subscription['uuid'] = str(uuid.uuid4())
        return subscription
