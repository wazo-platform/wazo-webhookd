# Copyright 2017-2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later


import logging

from xivo.rest_api_helpers import APIException

logger = logging.getLogger(__name__)


class TokenWithUserUUIDRequiredError(APIException):
    def __init__(self):
        super().__init__(
            status_code=400,
            message='A valid token with a user UUID is required',
            error_id='token-with-user-uuid-required',
        )
