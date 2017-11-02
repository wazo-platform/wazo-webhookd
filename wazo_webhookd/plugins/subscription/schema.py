# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from marshmallow import (
    pre_load,
    post_load
)
from marshmallow import Schema
from marshmallow import validates
from marshmallow import ValidationError
from xivo.mallow import fields
from xivo.mallow.validate import OneOf
from xivo.mallow.validate import Length

VALID_METHODS = ['head', 'get', 'post', 'put', 'delete']


class HTTPSubscriptionConfigSchema(Schema):
    body = fields.String(validate=Length(max=16384))
    method = fields.String(required=True, validate=Length(max=64))
    url = fields.String(required=True, validate=Length(max=8192))
    verify_certificate = fields.String(validate=Length(max=1024))
    content_type = fields.String(validate=Length(max=256))

    @pre_load
    def remove_none_values(self, config):
        optional_keys = (name for name, field in self.fields.items() if not field.required)
        for optional_key in optional_keys:
            if config.get(optional_key) is None:
                config.pop(optional_key, None)
        return config

    @post_load
    def lowercase_method(self, data):
        data['method'] = data['method'].lower()

    @validates('method')
    def validate_method(self, data):
        OneOf(VALID_METHODS)(data.lower())

    @validates('verify_certificate')
    def validate_verify(self, data):
        if data in ('true', 'false'):
            pass
        elif data.startswith('/'):
            pass
        else:
            raise ValidationError({
                'message': 'Wrong value for verify_certificate',
                'constraint_id': 'verify-certificate-invalid',
                'constraint': ['true', 'false', '/*'],
            })


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


class ConfigField(fields.Field):

    _default_options = fields.Dict(validate=validate_config_dict, allow_none=False, required=True)
    _options = {
        'http': fields.Nested(HTTPSubscriptionConfigSchema, required=True),
    }

    def _deserialize(self, value, attr, data):
        service = data.get('service')
        try:
            concrete_options = self._options.get(service, self._default_options)
        except TypeError:
            raise ValidationError({
                'message': 'Invalid destination',
                'constraint_id': 'destination-type',
                'constraint': {
                    'type': 'string',
                }
            })

        return concrete_options.deserialize(value, attr, data)


class SubscriptionSchema(Schema):
    uuid = fields.UUID(dump_only=True)
    name = fields.String(validate=Length(max=128), required=True)
    service = fields.String(validate=Length(max=128), allow_none=False, required=True)
    events = fields.List(fields.String(validate=Length(max=128), allow_none=False), allow_none=False, required=True)
    events_user_uuid = fields.String(validate=Length(equal=36), missing=None)
    events_wazo_uuid = fields.String(validate=Length(equal=36), missing=None)
    config = ConfigField(allow_none=False, required=True)
    owner_user_uuid = fields.String(validate=Length(equal=36), missing=None)


class UserSubscriptionSchema(Schema):
    uuid = fields.UUID(dump_only=True)
    name = fields.String(validate=Length(max=128), required=True)
    service = fields.String(validate=Length(max=128), allow_none=False, required=True)
    events = fields.List(fields.String(validate=Length(max=128), allow_none=False), allow_none=False, required=True)
    config = ConfigField(allow_none=False, required=True)


subscription_schema = SubscriptionSchema(strict=True)
user_subscription_schema = UserSubscriptionSchema(strict=True)
