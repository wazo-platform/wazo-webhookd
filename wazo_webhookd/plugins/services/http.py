# Copyright 2017-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from typing import TypedDict, TYPE_CHECKING

from wazo_webhookd.rest_api import AuthResource
from xivo.auth_verifier import required_acl

if TYPE_CHECKING:
    from stevedore import NamedExtensionManager


class ServicesDict(TypedDict):
    services: dict[str, dict]


class ServicesResource(AuthResource):
    def __init__(self, service_manager: NamedExtensionManager) -> None:
        self._service_manager = service_manager

    @required_acl('webhookd.subscriptions.services.read')
    def get(self) -> tuple[ServicesDict, int]:
        result: ServicesDict = {
            'services': {name: {} for name in self._service_manager.names()}
        }
        return result, 200
