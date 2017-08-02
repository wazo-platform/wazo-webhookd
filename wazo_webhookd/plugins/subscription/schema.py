# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from marshmallow import Schema
from marshmallow import ValidationError
from xivo.mallow import fields
from xivo.mallow.validate import OneOf
from xivo.mallow.validate import Length


class HTTPSubscriptionConfigSchema(Schema):
    body = fields.String(validate=Length(max=16384))
    method = fields.String(validate=OneOf(['head', 'get', 'post', 'put', 'delete']), required=True)
    url = fields.String(required=True)


def validate_config_dict(dict_):
    for key, value in dict_.items():
        if not (isinstance(key, str) and isinstance(value, str)):
            raise ValidationError({
                'message': 'Not a mapping with string keys and string values',
                'constraint_id': 'key-value-type',
                'constraint': 'string',
            })
        if len(key) > 128 or len(value) > 2048:
            raise ValidationError({
                'message': 'Key or value too long',
                'constraint_id': 'key-value-length',
                'constraint': {
                    'key-max': 128,
                    'value-max': 2048,
                }
            })


class ConfigField(fields.Nested):

    _default_options = fields.Dict(validate=validate_config_dict, allow_none=False, required=True)
    _options = {
        'http': fields.Nested(HTTPSubscriptionConfigSchema, required=True),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(Schema, *args, **kwargs)

    def _deserialize(self, value, attr, data):
        service = data.get('service')
        concrete_options = self._options.get(service, self._default_options)
        return concrete_options._deserialize(value, attr, data)

    def _validate(self, value):
        super()._validate(value)
        service = value.get('service')
        concrete_options = self._options.get(service, self._default_options)
        return concrete_options._validate(value)

    def _serialize(self, value, attr, obj):
        return value


class SubscriptionSchema(Schema):
    uuid = fields.UUID(dump_only=True)
    name = fields.String(validate=Length(max=128), required=True)
    service = fields.String(validate=Length(max=128), allow_none=False, required=True)
    events = fields.List(fields.String(validate=Length(max=128), allow_none=False), allow_none=False, required=True)
    config = ConfigField(allow_none=False, required=True)


subscription_schema = SubscriptionSchema(strict=True)
