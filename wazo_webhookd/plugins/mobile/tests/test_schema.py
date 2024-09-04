# Copyright 2023-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import json
import uuid

import pytest
from marshmallow import ValidationError

from ....services.mobile.plugin import NotificationType
from ..schema import notification_schema


def test_schema_invalid() -> None:
    data = {
        'notification_type': NotificationType.MESSAGE_RECEIVED,
        'user_uuid': 'abc',
        'extra': '',
    }
    with pytest.raises(ValidationError) as exec_info:
        notification_schema.loads(json.dumps(data))

    error: ValidationError = exec_info.value
    assert error.messages == {
        'notification_type': [
            f'The type "{NotificationType.MESSAGE_RECEIVED}" is a reserved type.'
        ],
        'user_uuid': ['Length must be 36.'],
        'title': ['Missing data for required field.'],
        'body': ['Missing data for required field.'],
        'extra': ['Not a valid mapping type.'],
    }


def test_schema_valid() -> None:
    input_data = {
        'notification_type': 'test',
        'user_uuid': str(uuid.uuid4()),
        'title': 'My title',
        'body': 'My body',
        'extra': {},
    }
    validated = notification_schema.loads(json.dumps(input_data))
    assert validated == input_data
