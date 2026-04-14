# Copyright 2017-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from xivo.auth_verifier import required_acl

from wazo_webhookd.rest_api import AuthResource

if TYPE_CHECKING:
    from xivo.status import StatusAggregator


class StatusResource(AuthResource):
    def __init__(self, status_aggregator: StatusAggregator) -> None:
        self._status_aggregator = status_aggregator

    @required_acl('webhookd.status.read')
    def get(self) -> tuple[dict, int]:
        return dict(self._status_aggregator.status()), 200
