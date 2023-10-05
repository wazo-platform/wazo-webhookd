# Copyright 2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import re
from typing import TypedDict, Any

from marshmallow import Schema, fields
from marshmallow.validate import Length, NoneOf, Regexp
from ...services.mobile.plugin import RESERVED_NOTIFICATION_TYPES


class NotificationDict(TypedDict):
    notification_type: str
    user_uuid: str
    title: str
    body: str
    extra: dict[str, Any]


class NotificationSchema(Schema):
    notification_type = fields.String(
        validate=(
            Length(min=1, max=100),
            NoneOf(
                RESERVED_NOTIFICATION_TYPES,
                error='The type "{input}" is a reserved type.',
            ),
            Regexp(r'^[a-z0-9_]+$', re.IGNORECASE),
        ),
        required=True,
    )
    user_uuid = fields.String(validate=Length(equal=36), required=True)
    title = fields.String(validate=Length(max=128), required=True)
    body = fields.String(validate=Length(max=250), required=True)
    extra = fields.Dict(missing=dict, default=dict)


notification_schema = NotificationSchema()
