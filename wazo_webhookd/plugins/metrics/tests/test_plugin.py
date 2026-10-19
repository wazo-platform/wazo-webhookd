# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from unittest.mock import Mock, patch

from ..plugin import Plugin as MetricsPlugin


@patch('wazo_webhookd.plugins.metrics.plugin.init_flask_metrics')
def test_load_plugin_instruments_the_app(init_flask_metrics: Mock) -> None:
    mock_api = Mock()

    MetricsPlugin().load({'api': mock_api})  # type: ignore

    init_flask_metrics.assert_called_once_with(mock_api.app, mock_api)
