# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wazo_webhookd.bus import BusConsumer
    from wazo_webhookd.types import PluginDependencyDict


class Plugin:
    _bus_consumer: BusConsumer

    def load(self, dependencies: PluginDependencyDict) -> None:
        self._bus_consumer = dependencies['bus_consumer']
