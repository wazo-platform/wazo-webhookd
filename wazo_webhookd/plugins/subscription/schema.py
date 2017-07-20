# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from marshmallow import fields
from marshmallow import Schema
from marshmallow.validate import OneOf
from marshmallow.validate import URL


class HTTPSubscriptionConfigSchema(Schema):
    method = fields.String(validate=OneOf(['get', 'post', 'put', 'delete']))
    url = fields.String(validate=URL(schemes={'http', 'https'}))


class ConfigField(fields.Nested):

    _options = {
        'http': fields.Nested(HTTPSubscriptionConfigSchema, missing=dict, required=False),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(Schema, *args, **kwargs)

    def _deserialize(self, value, attr, data):
        method = data.get('service')
        concrete_options = self._options.get(method)
        if not concrete_options:
            return {}
        return concrete_options._deserialize(value, attr, data)

    def _serialize(self, value, attr, obj):
        return value


class SubscriptionSchema(Schema):
    uuid = fields.UUID(dump_only=True)
    name = fields.String()
    service = fields.String(allow_none=False)
    events = fields.List(fields.String(allow_none=False))
    config = ConfigField()


subscription_schema = SubscriptionSchema(strict=True)
