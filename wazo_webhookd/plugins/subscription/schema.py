# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from marshmallow import fields
from marshmallow import Schema
from marshmallow import validate
from marshmallow import ValidationError


fields.Field.default_error_messages = {
    'required': {'message': fields.Field.default_error_messages['required'],
                 'constraint_id': 'required',
                 'constraint': 'required'},
    'null': {'message': fields.Field.default_error_messages['null'],
             'constraint_id': 'not_null',
             'constraint': 'not_null'},
}
fields.String.default_error_messages = {
    'invalid': {'message': fields.String.default_error_messages['invalid'],
                'constraint_id': 'type',
                'constraint': 'string'},
}
fields.List.default_error_messages = {
    'invalid': {'message': fields.List.default_error_messages['invalid'],
                'constraint_id': 'type',
                'constraint': 'list'},
}
fields.Dict.default_error_messages = {
    'invalid': {'message': fields.Dict.default_error_messages['invalid'],
                'constraint_id': 'type',
                'constraint': 'dict'},
}


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
