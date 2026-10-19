# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from xivo.flask.metrics import init_flask_metrics

if TYPE_CHECKING:
    from wazo_webhookd.types import PluginDependencyDict


class Plugin:
    def load(self, dependencies: PluginDependencyDict) -> None:
        api = dependencies['api']
        init_flask_metrics(api.app, api)
