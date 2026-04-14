# Copyright 2017-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from xivo.status import Status

from ... import auth
from .http import StatusResource

if TYPE_CHECKING:
    from xivo.status import StatusDict

    from ...bus import BusConsumer
    from ...types import PluginDependencyDict


def _make_bus_consumer_provider(
    bus_consumer: BusConsumer,
):
    def provide_bus_consumer_status(status: StatusDict) -> None:
        status['bus_consumer']['status'] = (
            Status.ok if bus_consumer.consumer_connected() else Status.fail
        )

    return provide_bus_consumer_status


def _provide_master_tenant_status(status: StatusDict) -> None:
    try:
        auth.get_master_tenant_uuid()
    except auth.MasterTenantNotInitializedException:
        status['master_tenant']['status'] = Status.fail
    else:
        status['master_tenant']['status'] = Status.ok


class Plugin:
    def load(self, dependencies: PluginDependencyDict) -> None:
        api = dependencies['api']
        status_aggregator = dependencies['status_aggregator']
        bus_consumer = dependencies['bus_consumer']

        status_aggregator.add_provider(_make_bus_consumer_provider(bus_consumer))
        status_aggregator.add_provider(_provide_master_tenant_status)

        api.add_resource(
            StatusResource, '/status', resource_class_args=[status_aggregator]
        )
