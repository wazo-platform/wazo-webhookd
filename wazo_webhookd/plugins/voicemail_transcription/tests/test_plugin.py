# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import Mock

from wazo_webhookd.plugins.voicemail_transcription.plugin import Plugin


class TestPlugin:
    def test_load_stores_bus_consumer(self) -> None:
        plugin = Plugin()
        bus_consumer = Mock()
        dependencies: dict = {
            'api': Mock(),
            'auth_client': Mock(),
            'bus_consumer': bus_consumer,
            'bus_publisher': Mock(),
            'config': Mock(),
            'service_manager': Mock(),
            'next_token_change_subscribe': Mock(),
        }

        plugin.load(dependencies)  # type: ignore[arg-type]

        assert plugin._bus_consumer is bus_consumer

    def test_load_subscribes_to_voicemail_events(self) -> None:
        plugin = Plugin()
        bus_consumer = Mock()
        dependencies: dict = {
            'api': Mock(),
            'auth_client': Mock(),
            'bus_consumer': bus_consumer,
            'bus_publisher': Mock(),
            'config': Mock(),
            'service_manager': Mock(),
            'next_token_change_subscribe': Mock(),
        }

        plugin.load(dependencies)  # type: ignore[arg-type]

        bus_consumer.subscribe.assert_any_call(
            'user_voicemail_message_created',
            plugin._on_user_voicemail_created,
        )
        bus_consumer.subscribe.assert_any_call(
            'global_voicemail_message_created',
            plugin._on_global_voicemail_created,
        )
        assert bus_consumer.subscribe.call_count == 2
