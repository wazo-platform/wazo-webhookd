# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from marshmallow import EXCLUDE, Schema

from xivo.mallow import fields


class ConfigSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    debug = fields.Boolean(allow_none=False)


config_schema = ConfigSchema()
