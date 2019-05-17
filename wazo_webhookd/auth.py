# -*- coding: utf-8 -*-
# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from flask import request
from requests import HTTPError
from xivo.auth_verifier import AuthServerUnreachable

from .exceptions import TokenWithUserUUIDRequiredError

logger = logging.getLogger(__name__)


def get_token_user_uuid_from_request(auth_client):
    token = request.headers.get("X-Auth-Token") or request.args.get("token")
    try:
        token_infos = auth_client.token.get(token)
    except HTTPError as e:
        logger.warning("HTTP error from wazo-auth while getting token: %s", e)
        raise TokenWithUserUUIDRequiredError()
    user_uuid = token_infos["xivo_user_uuid"]
    if not user_uuid:
        raise TokenWithUserUUIDRequiredError()
    return user_uuid


class Token:
    def __init__(self, auth_client, token_id):
        try:
            self._token_infos = auth_client.token.get(token_id)
        except HTTPError as e:
            logger.warning("HTTP error from wazo-auth while getting token: %s", e)
            raise AuthServerUnreachable(auth_client.host, auth_client.port, e)

    def user_uuid(self):
        user_uuid = self._token_infos["xivo_user_uuid"]
        if not user_uuid:
            raise TokenWithUserUUIDRequiredError()
        return user_uuid

    def wazo_uuid(self):
        return self._token_infos["xivo_uuid"]

    @classmethod
    def from_request(cls, auth_client):
        token_id = request.headers.get("X-Auth-Token") or request.args.get("token")
        return cls(auth_client, token_id)
