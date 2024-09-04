# Copyright 2023-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from unittest.mock import Mock, sentinel

from ..http import NotificationResource
from ..plugin import Plugin as MobilePlugin


def test_load_plugin() -> None:
    mock_api = Mock()
    dependencies = {
        'api': mock_api,
        'config': sentinel.config,
        'auth_client': sentinel.auth,
    }

    MobilePlugin().load(dependencies)  # type: ignore
    mock_api.add_resource.assert_called_once_with(
        NotificationResource,
        '/mobile/notifications',
        resource_class_args=[sentinel.config, sentinel.auth],
    )
