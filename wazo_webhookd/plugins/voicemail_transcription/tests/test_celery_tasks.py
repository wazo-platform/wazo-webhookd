# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
from celery.exceptions import Retry

from wazo_webhookd.plugins.voicemail_transcription.celery_tasks import (
    _parse_countdown,
    poll_transcription_job,
)


@pytest.fixture
def config() -> dict:
    return {
        'uuid': 'webhookd-uuid',
        'bus': {
            'username': 'guest',
            'password': 'guest',
            'host': 'localhost',
            'port': 5672,
            'exchange_name': 'wazo-headers',
            'exchange_type': 'headers',
        },
        'voicemail_transcription': {
            'service_url': 'https://scribed:1080',
            'max_poll_attempts': 10,
        },
    }


TASK_MODULE = 'wazo_webhookd.plugins.voicemail_transcription.celery_tasks'


class TestParseCountdown:
    def test_parses_future_datetime(self) -> None:
        future = datetime.now(tz=timezone.utc) + timedelta(seconds=30)
        result = _parse_countdown(future.isoformat())
        assert 28 <= result <= 31

    def test_clamps_past_datetime_to_1(self) -> None:
        past = datetime.now(tz=timezone.utc) - timedelta(seconds=10)
        result = _parse_countdown(past.isoformat())
        assert result == 1

    def test_none_returns_default(self) -> None:
        assert _parse_countdown(None) == 5

    def test_invalid_string_returns_default(self) -> None:
        assert _parse_countdown('not-a-date') == 5


class TestPollTranscriptionJob:
    @patch(f'{TASK_MODULE}.BusPublisher')
    @patch(f'{TASK_MODULE}.requests')
    def test_completed_job_does_not_retry(
        self, mock_requests: Mock, mock_bus_publisher_cls: Mock, config: dict
    ) -> None:
        mock_requests.get.return_value = Mock(
            status_code=200,
            json=Mock(return_value={'status': 'completed', 'job_id': 'job-1'}),
        )
        mock_requests.get.return_value.raise_for_status = Mock()

        poll_transcription_job(config, 'https://scribed:1080', 'job-1', 42, 'msg-1')

        mock_requests.get.assert_called_once_with(
            'https://scribed:1080/transcriptions/jobs/job-1'
        )

    @patch(f'{TASK_MODULE}.requests')
    def test_failed_job_does_not_retry(self, mock_requests: Mock, config: dict) -> None:
        mock_requests.get.return_value = Mock(
            status_code=200,
            json=Mock(
                return_value={
                    'status': 'failed',
                    'job_id': 'job-1',
                    'error': {'message': 'decode error'},
                }
            ),
        )
        mock_requests.get.return_value.raise_for_status = Mock()

        poll_transcription_job(config, 'https://scribed:1080', 'job-1', 42, 'msg-1')

    @patch(f'{TASK_MODULE}.requests')
    def test_pending_job_retries_with_countdown(
        self, mock_requests: Mock, config: dict
    ) -> None:
        future = datetime.now(tz=timezone.utc) + timedelta(seconds=20)
        mock_requests.get.return_value = Mock(
            status_code=200,
            json=Mock(
                return_value={
                    'status': 'pending',
                    'job_id': 'job-1',
                    'estimated_completion_at': future.isoformat(),
                }
            ),
        )
        mock_requests.get.return_value.raise_for_status = Mock()

        with patch.object(
            poll_transcription_job, 'retry', side_effect=Retry()
        ) as mock_retry:
            with pytest.raises(Retry):
                poll_transcription_job(
                    config, 'https://scribed:1080', 'job-1', 42, 'msg-1'
                )

            mock_retry.assert_called_once()
            call_kwargs = mock_retry.call_args[1]
            assert 18 <= call_kwargs['countdown'] <= 21

    @patch(f'{TASK_MODULE}.requests')
    def test_pending_without_estimated_uses_default_countdown(
        self, mock_requests: Mock, config: dict
    ) -> None:
        mock_requests.get.return_value = Mock(
            status_code=200,
            json=Mock(
                return_value={
                    'status': 'pending',
                    'job_id': 'job-1',
                }
            ),
        )
        mock_requests.get.return_value.raise_for_status = Mock()

        with patch.object(
            poll_transcription_job, 'retry', side_effect=Retry()
        ) as mock_retry:
            with pytest.raises(Retry):
                poll_transcription_job(
                    config, 'https://scribed:1080', 'job-1', 42, 'msg-1'
                )

            call_kwargs = mock_retry.call_args[1]
            assert call_kwargs['countdown'] == 5

    @patch(f'{TASK_MODULE}.BusPublisher')
    @patch(f'{TASK_MODULE}.requests')
    def test_sets_max_retries_from_config(
        self, mock_requests: Mock, mock_bus_publisher_cls: Mock, config: dict
    ) -> None:
        mock_requests.get.return_value = Mock(
            status_code=200,
            json=Mock(return_value={'status': 'completed', 'job_id': 'job-1'}),
        )
        mock_requests.get.return_value.raise_for_status = Mock()

        config['voicemail_transcription']['max_poll_attempts'] = 7

        poll_transcription_job(config, 'https://scribed:1080', 'job-1', 42, 'msg-1')

        assert poll_transcription_job.max_retries == 7

    @patch(f'{TASK_MODULE}.BusPublisher')
    @patch(f'{TASK_MODULE}.requests')
    def test_completed_job_publishes_bus_event(
        self, mock_requests: Mock, mock_bus_publisher_cls: Mock, config: dict
    ) -> None:
        completed_result = {
            'status': 'completed',
            'job_id': 'job-1',
            'transcription_items': [{'text': 'Hello world'}],
        }
        mock_requests.get.return_value = Mock(
            status_code=200,
            json=Mock(return_value=completed_result),
        )
        mock_requests.get.return_value.raise_for_status = Mock()
        mock_publisher = mock_bus_publisher_cls.from_config.return_value

        poll_transcription_job(config, 'https://scribed:1080', 'job-1', 42, 'msg-1')

        mock_bus_publisher_cls.from_config.assert_called_once_with(
            'webhookd-uuid', config['bus']
        )
        mock_publisher.publish.assert_called_once()
        event = mock_publisher.publish.call_args[0][0]
        assert event.name == 'voicemail_transcription_finished'
        assert event.content['voicemail_id'] == 42
        assert event.content['message_id'] == 'msg-1'
        assert event.content['transcription_items'] == [{'text': 'Hello world'}]

    @patch(f'{TASK_MODULE}.BusPublisher')
    @patch(f'{TASK_MODULE}.requests')
    def test_failed_job_does_not_publish(
        self, mock_requests: Mock, mock_bus_publisher_cls: Mock, config: dict
    ) -> None:
        mock_requests.get.return_value = Mock(
            status_code=200,
            json=Mock(
                return_value={
                    'status': 'failed',
                    'job_id': 'job-1',
                    'error': {'message': 'decode error'},
                }
            ),
        )
        mock_requests.get.return_value.raise_for_status = Mock()

        poll_transcription_job(config, 'https://scribed:1080', 'job-1', 42, 'msg-1')

        mock_bus_publisher_cls.from_config.assert_not_called()
