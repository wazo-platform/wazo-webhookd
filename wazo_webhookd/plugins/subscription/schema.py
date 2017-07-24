# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from marshmallow import fields
from marshmallow import Schema
from marshmallow import validate


class Length(validate.Length):

    constraint_id = 'length'

    def _format_error(self, value, message):
        msg = super()._format_error(value, message)

        return {
            'constraint_id': self.constraint_id,
            'constraint': {'min': self.min, 'max': self.max},
            'message': msg,
        }


class OneOf(validate.OneOf):

    constraint_id = 'enum'

    def _format_error(self, value):
        msg = super()._format_error(value)

        return {
            'constraint_id': self.constraint_id,
            'constraint': {'choices': self.choices},
            'message': msg,
        }


class URL(validate.URL):

    constraint_id = 'url'

    def _format_error(self, value):
        msg = super()._format_error(value)

        return {
            'constraint_id': self.constraint_id,
            'constraint': {'schemes': list(self.schemes)},
            'message': msg,
        }


class HTTPSubscriptionConfigSchema(Schema):
    method = fields.String(validate=OneOf(['get', 'post', 'put', 'delete']), required=True)
    url = fields.String(validate=URL(schemes={'http', 'https'}), required=True)


class StringDictField(fields.Dict):

    default_error_messages = {
        'invalid': 'Not a mapping with string keys and string values',
        'too-long': 'Key (limit: 128) or value (limit: 2048) too long'
    }

    def _deserialize(self, value, attr, obj):
        dict_ = super()._deserialize(value, attr, obj)
        for key, value in dict_.items():
            if not (isinstance(key, str) and isinstance(value, str)):
                self.fail('invalid')
            if len(key) > 128:
                self.fail('too-long')
            if len(value) > 2048:
                self.fail('too-long')
        return dict_


class ConfigField(fields.Nested):

    _default_options = StringDictField(allow_none=False, required=True)
    _options = {
        'http': fields.Nested(HTTPSubscriptionConfigSchema, required=True),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(Schema, *args, **kwargs)

    def _deserialize(self, value, attr, data):
        service = data.get('service')
        concrete_options = self._options.get(service, self._default_options)
        return concrete_options._deserialize(value, attr, data)

    def _serialize(self, value, attr, obj):
        return value


class SubscriptionSchema(Schema):
    uuid = fields.UUID(dump_only=True)
    name = fields.String(validate=Length(max=128), required=True)
    service = fields.String(validate=Length(max=128), allow_none=False, required=True)
    events = fields.List(fields.String(validate=Length(max=128), allow_none=False), allow_none=False, required=True)
    config = ConfigField(allow_none=False, required=True)


subscription_schema = SubscriptionSchema(strict=True)
