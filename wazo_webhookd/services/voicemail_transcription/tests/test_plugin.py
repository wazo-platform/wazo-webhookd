# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import Mock, call, patch

from wazo_webhookd.services.voicemail_transcription.plugin import Plugin

CALLD_CONFIG = {
    'host': 'localhost',
    'port': 9500,
    'prefix': None,
    'https': False,
    'verify_certificate': False,
}

CONFD_CONFIG = {
    'host': 'localhost',
    'port': 9486,
    'prefix': None,
    'https': False,
    'verify_certificate': False,
}


class TestPlugin:
    def _make_dependencies(self) -> dict:
        return {
            'api': Mock(),
            'auth_client': Mock(),
            'bus_consumer': Mock(),
            'bus_publisher': Mock(),
            'config': {
                'calld': CALLD_CONFIG,
                'confd': CONFD_CONFIG,
            },
            'token_change_subscribe': Mock(),
        }

    @patch('wazo_webhookd.services.voicemail_transcription.plugin.ConfdClient')
    @patch('wazo_webhookd.services.voicemail_transcription.plugin.CalldClient')
    @patch(
        'wazo_webhookd.services.voicemail_transcription.plugin.VoicemailTranscriptionHandler'
    )
    def test_load_subscribes_clients_to_token_renewal(
        self, MockHandler: Mock, MockCalldClient: Mock, MockConfdClient: Mock
    ) -> None:
        plugin = Plugin()
        deps = self._make_dependencies()

        plugin.load(deps)  # type: ignore[arg-type]

        deps['token_change_subscribe'].assert_has_calls(
            [
                call(MockCalldClient.return_value.set_token),
                call(MockConfdClient.return_value.set_token),
            ],
            any_order=True,
        )

    @patch('wazo_webhookd.services.voicemail_transcription.plugin.ConfdClient')
    @patch('wazo_webhookd.services.voicemail_transcription.plugin.CalldClient')
    @patch(
        'wazo_webhookd.services.voicemail_transcription.plugin.VoicemailTranscriptionHandler'
    )
    def test_load_subscribes_handler_to_voicemail_events(
        self, MockHandler: Mock, MockCalldClient: Mock, MockConfdClient: Mock
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
