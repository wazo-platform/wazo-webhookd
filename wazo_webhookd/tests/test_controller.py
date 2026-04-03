# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture
def mock_dependencies():
    with (
        patch('wazo_webhookd.controller.celery') as mock_celery,
        patch('wazo_webhookd.controller.AuthClient') as mock_auth_client_cls,
        patch('wazo_webhookd.controller.TokenRenewer') as mock_token_renewer_cls,
        patch('wazo_webhookd.controller.BusConsumer') as mock_bus_consumer_cls,
        patch('wazo_webhookd.controller.BusPublisher') as mock_bus_publisher_cls,
        patch('wazo_webhookd.controller.CoreRestApi') as mock_rest_api_cls,
        patch('wazo_webhookd.controller.plugin_helpers') as mock_plugin_helpers,
    ):
        mock_token_renewer = mock_token_renewer_cls.return_value
        yield {
            'celery': mock_celery,
            'auth_client_cls': mock_auth_client_cls,
            'token_renewer_cls': mock_token_renewer_cls,
            'token_renewer': mock_token_renewer,
            'bus_consumer_cls': mock_bus_consumer_cls,
            'bus_publisher_cls': mock_bus_publisher_cls,
            'rest_api_cls': mock_rest_api_cls,
            'plugin_helpers': mock_plugin_helpers,
        }


def _make_config() -> dict:
    return {
        'uuid': 'test-uuid',
        'consul': {},
        'service_discovery': {},
        'bus': {},
        'auth': {'host': 'localhost', 'port': 9497},
        'enabled_services': {'http': True},
        'enabled_plugins': {'subscription': True},
    }


class TestController:
    def test_service_dependencies_include_token_change_subscribe(
        self, mock_dependencies
    ) -> None:
        from wazo_webhookd.controller import Controller

        config = _make_config()
        Controller(config)  # type: ignore[arg-type]

        calls = mock_dependencies['plugin_helpers'].load.call_args_list
        service_load_call = calls[0]
        assert service_load_call.kwargs['namespace'] == 'wazo_webhookd.services'

        deps = service_load_call.kwargs['dependencies']
        assert 'token_change_subscribe' in deps
        assert (
            deps['token_change_subscribe']
            == mock_dependencies['token_renewer'].subscribe_to_token_change
        )
