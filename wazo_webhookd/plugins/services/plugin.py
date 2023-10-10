# Copyright 2017-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING

from .http import ServicesResource

if TYPE_CHECKING:
    from ...types import PluginDependencyDict


class Plugin:
    def load(self, dependencies: PluginDependencyDict) -> None:
        api = dependencies['api']
        services_manager = dependencies['service_manager']
        api.add_resource(
            ServicesResource,
            '/subscriptions/services',
            resource_class_args=[services_manager],
        )
