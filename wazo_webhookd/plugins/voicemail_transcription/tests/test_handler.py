from __future__ import annotations

from collections import ChainMap
from unittest.mock import Mock, patch

from ..handler import VoicemailTranscriptionHandler


@patch(
    'wazo_webhookd.plugins.voicemail_transcription.handler.transcribe_voicemail_task'
)
def test_on_user_voicemail_created_serializes_config(mock_task: Mock) -> None:
    config = ChainMap({'voicemail_transcription': {'service_url': 'http://service'}})
    handler = VoicemailTranscriptionHandler(config)  # type: ignore[arg-type]

    handler.on_user_voicemail_created(
        {
            'data': {
                'voicemail_id': 12,
                'message_id': '34',
                'user_uuid': 'user-uuid',
            }
        },
        {},
    )

    mock_task.delay.assert_called_once()
    args, kwargs = mock_task.delay.call_args
    assert type(args[0]) is dict
    assert args == (dict(config), 12, '34')
    assert kwargs == {'user_uuid': 'user-uuid', 'require_license_check': True}


@patch(
    'wazo_webhookd.plugins.voicemail_transcription.handler.transcribe_voicemail_task'
)
def test_on_global_voicemail_created_serializes_config(mock_task: Mock) -> None:
    config = ChainMap({'voicemail_transcription': {'service_url': 'http://service'}})
    handler = VoicemailTranscriptionHandler(config)  # type: ignore[arg-type]

    handler.on_global_voicemail_created(
        {
            'data': {
                'voicemail_id': 12,
                'message_id': '34',
            }
        },
        {},
    )

    mock_task.delay.assert_called_once()
    args, kwargs = mock_task.delay.call_args
    assert type(args[0]) is dict
    assert args == (dict(config), 12, '34')
    assert kwargs == {'user_uuid': None, 'require_license_check': False}
