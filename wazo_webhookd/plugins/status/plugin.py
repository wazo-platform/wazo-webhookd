# Copyright 2017-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from .http import StatusResource

if TYPE_CHECKING:
    from ...types import PluginDependencyDict


class Plugin:
    def load(self, dependencies: PluginDependencyDict) -> None:
        api = dependencies['api']
        bus_consumer = dependencies['bus_consumer']
        config = dependencies['config']

        api.add_resource(
            StatusResource, '/status', resource_class_args=[bus_consumer, config]
        )
