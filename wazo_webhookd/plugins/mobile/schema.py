# Copyright 2023-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import re
from typing import Any, TypedDict

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
    # There is no technical reason for this character limit,
    # but anything approaching this limit will not be displayed.
    # The only technical limit on the payload is a max total size of 2KB.
    title = fields.String(validate=Length(max=128), required=True)
    body = fields.String(validate=Length(max=250), required=True)
    extra = fields.Dict(load_default=dict, dump_default=dict)


notification_schema = NotificationSchema()
