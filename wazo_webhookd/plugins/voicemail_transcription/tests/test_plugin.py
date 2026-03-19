# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import Mock, patch

from wazo_webhookd.plugins.voicemail_transcription.plugin import Plugin


class TestPlugin:
    def _make_dependencies(self) -> dict:
        return {
            'api': Mock(),
            'auth_client': Mock(),
            'bus_consumer': Mock(),
            'bus_publisher': Mock(),
            'config': {
                'calld': {
                    'host': 'localhost',
                    'port': 9500,
                    'prefix': None,
                    'https': False,
                    'verify_certificate': False,
                },
            },
            'service_manager': Mock(),
            'next_token_change_subscribe': Mock(),
        }

    @patch(
        'wazo_webhookd.plugins.voicemail_transcription.plugin.VoicemailTranscriptionHandler'
    )
    def test_load_creates_handler_with_config_and_auth(self, MockHandler: Mock) -> None:
        plugin = Plugin()
        deps = self._make_dependencies()

        plugin.load(deps)  # type: ignore[arg-type]

        MockHandler.assert_called_once_with(deps['config'], deps['auth_client'])

    @patch(
        'wazo_webhookd.plugins.voicemail_transcription.plugin.VoicemailTranscriptionHandler'
    )
    def test_load_subscribes_handler_to_voicemail_events(
        self, MockHandler: Mock
    ) -> None:
        plugin = Plugin()
        deps = self._make_dependencies()
        handler = MockHandler.return_value

        plugin.load(deps)  # type: ignore[arg-type]

        bus_consumer = deps['bus_consumer']
        bus_consumer.subscribe.assert_any_call(
            'user_voicemail_message_created',
            handler.on_user_voicemail_created,
        )
        bus_consumer.subscribe.assert_any_call(
            'global_voicemail_message_created',
            handler.on_global_voicemail_created,
        )
        assert bus_consumer.subscribe.call_count == 2
