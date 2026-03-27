# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from collections import ChainMap
from collections.abc import Generator
from unittest.mock import Mock, patch

import pytest

from wazo_webhookd.services.voicemail_transcription.handler import (
    VoicemailTranscriptionHandler,
)

TENANT_UUID = 'tenant-uuid-1'


@pytest.fixture
def calld_client() -> Mock:
    client = Mock()
    client.voicemails.get_voicemail_recording.return_value = b'audio-data'
    return client


@pytest.fixture
def confd_client() -> Mock:
    client = Mock()
    client.voicemail_transcription.get.return_value = {'enabled': True}
    return client


@pytest.fixture
def config() -> ChainMap:
    return ChainMap(
        {
            'calld': {
                'host': 'localhost',
                'port': 9500,
                'prefix': None,
                'https': False,
                'verify_certificate': False,
            },
            'voicemail_transcription': {
                'service_url': 'https://scribed:1080',
            },
        }
    )


@pytest.fixture
def mock_requests() -> Generator[Mock, None, None]:
    with patch(
        'wazo_webhookd.services.voicemail_transcription.handler.requests'
    ) as mock_req:
        mock_req.post.return_value = Mock(
            status_code=202,
            json=Mock(
                return_value={
                    'job_id': 'job-abc',
                    'status': 'pending',
                    'estimated_completion_at': '2026-01-01T00:00:30+00:00',
                }
            ),
        )
        mock_req.post.return_value.raise_for_status = Mock()
        yield mock_req


@pytest.fixture
def mock_poll_task() -> Generator[Mock, None, None]:
    with patch(
        'wazo_webhookd.services.voicemail_transcription.handler.poll_transcription_job'
    ) as mock_task:
        yield mock_task


@pytest.fixture
def handler(
    config: ChainMap,
    calld_client: Mock,
    confd_client: Mock,
    mock_requests: Mock,
    mock_poll_task: Mock,
) -> VoicemailTranscriptionHandler:
    return VoicemailTranscriptionHandler(
        config, calld_client, confd_client  # type: ignore[arg-type]
    )


class TestOnUserVoicemailCreated:
    def test_fetches_recording(self, handler: VoicemailTranscriptionHandler) -> None:
        payload = {
            'data': {
                'voicemail_id': 42,
                'message_id': 'msg-123',
                'user_uuid': 'user-uuid-1',
            }
        }
        headers = {'tenant_uuid': TENANT_UUID}

        handler.on_user_voicemail_created(payload, headers)

        handler._calld_client.voicemails.get_voicemail_recording.assert_called_once_with(
            42, 'msg-123'
        )

    def test_missing_voicemail_id_skips(
        self, handler: VoicemailTranscriptionHandler
    ) -> None:
        payload = {'data': {'message_id': 'msg-1', 'user_uuid': 'user-1'}}
        headers = {'tenant_uuid': TENANT_UUID}

        handler.on_user_voicemail_created(payload, headers)

        handler._calld_client.voicemails.get_voicemail_recording.assert_not_called()

    def test_missing_message_id_skips(
        self, handler: VoicemailTranscriptionHandler
    ) -> None:
        payload = {'data': {'voicemail_id': 42, 'user_uuid': 'user-1'}}
        headers = {'tenant_uuid': TENANT_UUID}

        handler.on_user_voicemail_created(payload, headers)

        handler._calld_client.voicemails.get_voicemail_recording.assert_not_called()

    def test_submits_recording_to_scribed(
        self, handler: VoicemailTranscriptionHandler, mock_requests: Mock
    ) -> None:
        handler._calld_client.voicemails.get_voicemail_recording.return_value = (
            b'user-audio'
        )
        payload = {
            'data': {
                'voicemail_id': 42,
                'message_id': 'msg-123',
                'user_uuid': 'user-uuid-1',
            }
        }
        headers = {'tenant_uuid': TENANT_UUID}

        handler.on_user_voicemail_created(payload, headers)

        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        assert call_args[0][0] == 'https://scribed:1080/transcriptions/jobs'
        assert 'files' in call_args[1]
        assert call_args[1]['files']['audio'][1] == b'user-audio'

    def test_dispatches_poll_task_after_submission(
        self,
        handler: VoicemailTranscriptionHandler,
        mock_poll_task: Mock,
        config: dict,
    ) -> None:
        payload = {
            'data': {
                'voicemail_id': 42,
                'message_id': 'msg-123',
                'user_uuid': 'user-uuid-1',
            }
        }
        headers = {'tenant_uuid': TENANT_UUID}

        handler.on_user_voicemail_created(payload, headers)

        mock_poll_task.apply_async.assert_called_once()
        call_kwargs = mock_poll_task.apply_async.call_args[1]
        assert call_kwargs['kwargs']['job_id'] == 'job-abc'
        assert call_kwargs['kwargs']['voicemail_id'] == 42
        assert call_kwargs['kwargs']['message_id'] == 'msg-123'
        assert call_kwargs['kwargs']['service_url'] == 'https://scribed:1080'
        assert call_kwargs['kwargs']['tenant_uuid'] == TENANT_UUID
        assert type(call_kwargs['kwargs']['config']) is dict
        assert call_kwargs['kwargs']['config'] == dict(config)
        assert isinstance(call_kwargs['countdown'], int)

    def test_skips_when_transcription_not_enabled(
        self, handler: VoicemailTranscriptionHandler, confd_client: Mock
    ) -> None:
        confd_client.voicemail_transcription.get.return_value = {'enabled': False}
        payload = {
            'data': {
                'voicemail_id': 42,
                'message_id': 'msg-123',
                'user_uuid': 'user-uuid-1',
            }
        }
        headers = {'tenant_uuid': TENANT_UUID}

        handler.on_user_voicemail_created(payload, headers)

        handler._calld_client.voicemails.get_voicemail_recording.assert_not_called()

    def test_skips_when_tenant_uuid_missing_from_headers(
        self, handler: VoicemailTranscriptionHandler
    ) -> None:
        payload = {
            'data': {
                'voicemail_id': 42,
                'message_id': 'msg-123',
                'user_uuid': 'user-uuid-1',
            }
        }
        headers: dict = {}

        handler.on_user_voicemail_created(payload, headers)

        handler._calld_client.voicemails.get_voicemail_recording.assert_not_called()

    def test_checks_tenant_permission_via_confd(
        self, handler: VoicemailTranscriptionHandler, confd_client: Mock
    ) -> None:
        payload = {
            'data': {
                'voicemail_id': 42,
                'message_id': 'msg-123',
                'user_uuid': 'user-uuid-1',
            }
        }
        headers = {'tenant_uuid': TENANT_UUID}

        handler.on_user_voicemail_created(payload, headers)

        confd_client.voicemail_transcription.get.assert_called_once_with(
            tenant_uuid=TENANT_UUID
        )


class TestOnGlobalVoicemailCreated:
    def test_fetches_recording(self, handler: VoicemailTranscriptionHandler) -> None:
        payload = {
            'data': {
                'voicemail_id': 99,
                'message_id': 'msg-456',
            }
        }
        headers = {'tenant_uuid': TENANT_UUID}

        handler.on_global_voicemail_created(payload, headers)

        handler._calld_client.voicemails.get_voicemail_recording.assert_called_once_with(
            99, 'msg-456'
        )

    def test_missing_voicemail_id_skips(
        self, handler: VoicemailTranscriptionHandler
    ) -> None:
        payload = {'data': {'message_id': 'msg-1'}}
        headers = {'tenant_uuid': TENANT_UUID}

        handler.on_global_voicemail_created(payload, headers)

        handler._calld_client.voicemails.get_voicemail_recording.assert_not_called()

    def test_submits_recording_to_scribed(
        self, handler: VoicemailTranscriptionHandler, mock_requests: Mock
    ) -> None:
        handler._calld_client.voicemails.get_voicemail_recording.return_value = (
            b'global-audio'
        )
        payload = {
            'data': {
                'voicemail_id': 99,
                'message_id': 'msg-456',
            }
        }
        headers = {'tenant_uuid': TENANT_UUID}

        handler.on_global_voicemail_created(payload, headers)

        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        assert call_args[0][0] == 'https://scribed:1080/transcriptions/jobs'
        assert call_args[1]['files']['audio'][1] == b'global-audio'

    def test_skips_when_transcription_not_enabled(
        self, handler: VoicemailTranscriptionHandler, confd_client: Mock
    ) -> None:
        confd_client.voicemail_transcription.get.return_value = {'enabled': False}
        payload = {
            'data': {
                'voicemail_id': 99,
                'message_id': 'msg-456',
            }
        }
        headers = {'tenant_uuid': TENANT_UUID}

        handler.on_global_voicemail_created(payload, headers)

        handler._calld_client.voicemails.get_voicemail_recording.assert_not_called()
