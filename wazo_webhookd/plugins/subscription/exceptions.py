# Copyright 2017-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from xivo.rest_api_helpers import APIException


class NoSuchSubscription(APIException):
    def __init__(self, subscription_uuid: str) -> None:
        super().__init__(
            status_code=404,
            message=f'No such subscription: {subscription_uuid}',
            error_id='no-such-subscription',
            details={'subscription_uuid': subscription_uuid},
        )
