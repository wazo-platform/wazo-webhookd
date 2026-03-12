# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from wazo_webhookd.plugins.voicemail_transcription.handler import (
    VoicemailTranscriptionHandler,
)


@pytest.fixture
def auth_client() -> Mock:
    client = Mock()
    client.token.new.return_value = {'token': 'some-token'}
    return client


@pytest.fixture
def config() -> dict:
    return {
        'calld': {
            'host': 'localhost',
            'port': 9500,
            'prefix': None,
            'https': False,
            'verify_certificate': False,
        },
    }


@pytest.fixture
def handler(config: dict, auth_client: Mock) -> VoicemailTranscriptionHandler:
    with patch(
        'wazo_webhookd.plugins.voicemail_transcription.handler.CalldClient'
    ) as MockCalldClient:
        h = VoicemailTranscriptionHandler(config, auth_client)  # type: ignore[arg-type]
        h._calld_client = MockCalldClient.return_value
    return h


class TestOnUserVoicemailCreated:
    def test_fetches_recording(
        self, handler: VoicemailTranscriptionHandler, auth_client: Mock
    ) -> None:
        payload = {
            'data': {
                'voicemail_id': 42,
                'message_id': 'msg-123',
                'user_uuid': 'user-uuid-1',
            }
        }

        handler.on_user_voicemail_created(payload)

        auth_client.token.new.assert_called_once()
        handler._calld_client.voicemails.get_voicemail_recording.assert_called_once_with(
            42, 'msg-123'
        )

    def test_sets_token_on_calld_client(
        self, handler: VoicemailTranscriptionHandler, auth_client: Mock
    ) -> None:
        auth_client.token.new.return_value = {'token': 'fresh-token'}
        payload = {
            'data': {
                'voicemail_id': 1,
                'message_id': 'msg-1',
                'user_uuid': 'user-1',
            }
        }

        handler.on_user_voicemail_created(payload)

        assert handler._calld_client.set_token.call_args[0][0] == 'fresh-token'

    def test_missing_voicemail_id_skips(
        self, handler: VoicemailTranscriptionHandler
    ) -> None:
        payload = {'data': {'message_id': 'msg-1', 'user_uuid': 'user-1'}}

        handler.on_user_voicemail_created(payload)

        handler._calld_client.voicemails.get_voicemail_recording.assert_not_called()

    def test_missing_message_id_skips(
        self, handler: VoicemailTranscriptionHandler
    ) -> None:
        payload = {'data': {'voicemail_id': 42, 'user_uuid': 'user-1'}}

        handler.on_user_voicemail_created(payload)

        handler._calld_client.voicemails.get_voicemail_recording.assert_not_called()


class TestOnGlobalVoicemailCreated:
    def test_fetches_recording(
        self, handler: VoicemailTranscriptionHandler, auth_client: Mock
    ) -> None:
        payload = {
            'data': {
                'voicemail_id': 99,
                'message_id': 'msg-456',
            }
        }

        handler.on_global_voicemail_created(payload)

        auth_client.token.new.assert_called_once()
        handler._calld_client.voicemails.get_voicemail_recording.assert_called_once_with(
            99, 'msg-456'
        )

    def test_missing_voicemail_id_skips(
        self, handler: VoicemailTranscriptionHandler
    ) -> None:
        payload = {'data': {'message_id': 'msg-1'}}

        handler.on_global_voicemail_created(payload)

        handler._calld_client.voicemails.get_voicemail_recording.assert_not_called()
