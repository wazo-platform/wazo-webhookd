from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from ..celery_tasks import transcribe_voicemail_task


@patch(
    'wazo_webhookd.plugins.voicemail_transcription.celery_tasks.get_transcription_result'
)
@patch('wazo_webhookd.plugins.voicemail_transcription.celery_tasks.get_auth_token')
def test_polling_does_not_fetch_auth_token(
    mock_get_auth_token: Mock,
    mock_get_transcription_result: Mock,
) -> None:
    mock_get_transcription_result.return_value = {'status': 'processing'}
    with patch.object(
        transcribe_voicemail_task, 'retry', side_effect=RuntimeError('retry')
    ) as mock_retry:
        with pytest.raises(RuntimeError):
            transcribe_voicemail_task.run(
                {
                    'auth': {},
                    'voicemail_transcription': {'service_url': 'http://service'},
                },  # type: ignore[arg-type]
                12,
                '34',
                user_uuid='user-uuid',
                require_license_check=False,
                job_id='job-123',
            )

    mock_get_auth_token.assert_not_called()
    mock_get_transcription_result.assert_called_once_with('http://service', 'job-123')
    mock_retry.assert_called_once()


@patch('wazo_webhookd.plugins.voicemail_transcription.celery_tasks.logger')
@patch(
    'wazo_webhookd.plugins.voicemail_transcription.celery_tasks.get_transcription_result'
)
@patch('wazo_webhookd.plugins.voicemail_transcription.celery_tasks.get_auth_token')
def test_completed_transcription_logs_result(
    mock_get_auth_token: Mock,
    mock_get_transcription_result: Mock,
    mock_logger: Mock,
) -> None:
    transcription_result = {'status': 'completed', 'transcript': 'hello world'}
    mock_get_transcription_result.return_value = transcription_result

    transcribe_voicemail_task.run(
        {
            'auth': {},
            'voicemail_transcription': {'service_url': 'http://service'},
        },  # type: ignore[arg-type]
        12,
        '34',
        job_id='job-123',
    )

    mock_logger.info.assert_called_once_with(
        'Transcription completed for voicemail %s, message %s: %s',
        12,
        '34',
        transcription_result,
    )
    mock_get_auth_token.assert_not_called()
