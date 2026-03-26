# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from mockserver import MockServerClient
from wazo_test_helpers import until

from .helpers.base import MASTER_TENANT, MASTER_TOKEN, BaseIntegrationTest
from .helpers.wait_strategy import ConnectedWaitStrategy

VOICEMAIL_ID = 42
MESSAGE_ID = 'msg-123'
USER_UUID = 'user-uuid-1'
TENANT_UUID = MASTER_TENANT

FAKE_AUDIO = b'\x00\x01\x02\x03'

REQUEST_TIMEOUT = 30


def _calld_recording_expectation(voicemail_id: int, message_id: str) -> dict:
    return {
        'httpRequest': {
            'method': 'GET',
            'path': f'/1.0/voicemails/{voicemail_id}/messages/{message_id}/recording',
        },
        'httpResponse': {
            'statusCode': 200,
            'headers': [
                {'name': 'Content-Type', 'values': ['audio/wav']},
            ],
            'body': {
                'type': 'BINARY',
                'base64Bytes': 'AAECAw==',
            },
        },
        'times': {'remainingTimes': 1, 'unlimited': False},
    }


def _scribed_job_creation_expectation(job_id: str = '1') -> dict:
    now = datetime.now(tz=timezone.utc)
    return {
        'httpRequest': {
            'method': 'POST',
            'path': '/transcriptions/jobs',
        },
        'httpResponse': {
            'statusCode': 202,
            'headers': [
                {
                    'name': 'Content-Type',
                    'values': ['application/json; charset=utf-8'],
                },
                {
                    'name': 'Location',
                    'values': [f'/transcriptions/jobs/{job_id}'],
                },
            ],
            'body': json.dumps(
                {
                    'job_id': job_id,
                    'status': 'pending',
                    'submitted_at': now.isoformat(),
                    'expires_at': (now + timedelta(hours=1)).isoformat(),
                    'estimated_completion_at': now.isoformat(),
                }
            ),
        },
        'times': {'remainingTimes': 1, 'unlimited': False},
    }


def _scribed_poll_expectation(
    job_id: str = '1',
    status: str = 'completed',
    error: dict | None = None,
) -> dict:
    now = datetime.now(tz=timezone.utc)
    base_fields: dict = {
        'job_id': job_id,
        'status': status,
        'submitted_at': (now - timedelta(seconds=10)).isoformat(),
        'expires_at': (now + timedelta(minutes=50)).isoformat(),
    }

    if status == 'completed':
        completed_at = now.isoformat()
        body = {
            **base_fields,
            'completed_at': completed_at,
            'total_processing_time_ms': 8000,
            'transcriptions_items': [
                {
                    'id': 'item-1',
                    'filename': 'voicemail.wav',
                    'status': 'completed',
                    'transcription': {
                        'text': 'Hello world',
                        'language': 'en',
                        'duration': 3.5,
                        'provider_id': 'test-provider',
                    },
                    'completed_at': completed_at,
                    'processing_time_ms': 8000,
                }
            ],
        }
        status_code = 201
    elif status == 'failed':
        body = {
            **base_fields,
            'failed_at': now.isoformat(),
            'error': error
            or {
                'code': 'AUDIO_DECODE_ERROR',
                'message': 'decode error',
                'retryable': False,
            },
        }
        status_code = 200
    else:
        body = {
            **base_fields,
            'estimated_completion_at': (now + timedelta(seconds=5)).isoformat(),
        }
        status_code = 200

    return {
        'httpRequest': {
            'method': 'GET',
            'path': f'/transcriptions/jobs/{job_id}',
        },
        'httpResponse': {
            'statusCode': status_code,
            'headers': [
                {
                    'name': 'Content-Type',
                    'values': ['application/json; charset=utf-8'],
                },
            ],
            'body': json.dumps(body),
        },
        'times': {'unlimited': True},
    }


def _confd_transcription_enabled_expectation(enabled: bool = True) -> dict:
    return {
        'httpRequest': {
            'method': 'GET',
            'path': '/1.1/voicemails/transcription',
        },
        'httpResponse': {
            'statusCode': 200,
            'headers': [
                {
                    'name': 'Content-Type',
                    'values': ['application/json; charset=utf-8'],
                },
            ],
            'body': json.dumps({'enabled': enabled}),
        },
        'times': {'unlimited': True},
    }


class TestVoicemailTranscription(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = ConnectedWaitStrategy()

    def setUp(self) -> None:
        super().setUp()
        self.calld_mock = self.make_calld_mock()
        self.calld_mock.reset()
        self.confd_mock = self.make_confd_mock()
        self.confd_mock.reset()
        self.scribed_mock = self.make_scribed_mock()
        self.scribed_mock.reset()
        self.bus = self.make_bus()
        until.true(self.bus.is_up, timeout=30, message='bus not ready')
        self.confd_mock.mock_any_response(_confd_transcription_enabled_expectation())

    def _publish_user_voicemail_event(
        self,
        voicemail_id: int = VOICEMAIL_ID,
        message_id: str = MESSAGE_ID,
    ) -> None:
        event = {
            'name': 'user_voicemail_message_created',
            'data': {
                'voicemail_id': voicemail_id,
                'message_id': message_id,
                'user_uuid': USER_UUID,
            },
        }
        self.bus.publish(
            event,
            headers={
                'name': 'user_voicemail_message_created',
                'tenant_uuid': TENANT_UUID,
            },
        )

    def _publish_global_voicemail_event(
        self,
        voicemail_id: int = VOICEMAIL_ID,
        message_id: str = MESSAGE_ID,
    ) -> None:
        event = {
            'name': 'global_voicemail_message_created',
            'data': {
                'voicemail_id': voicemail_id,
                'message_id': message_id,
            },
        }
        self.bus.publish(
            event,
            headers={
                'name': 'global_voicemail_message_created',
                'tenant_uuid': TENANT_UUID,
            },
        )

    def _assert_mock_verified(
        self,
        mock: MockServerClient,
        request: dict,
        timeout: int = REQUEST_TIMEOUT,
    ) -> None:
        def _verify() -> None:
            try:
                mock.verify(request=request)
            except Exception as e:
                raise AssertionError(str(e)) from e

        until.assert_(_verify, timeout=timeout, interval=1)

    def test_user_voicemail_event_triggers_transcription(self) -> None:
        self.calld_mock.mock_any_response(
            _calld_recording_expectation(VOICEMAIL_ID, MESSAGE_ID)
        )
        self.scribed_mock.mock_any_response(_scribed_job_creation_expectation())
        self.scribed_mock.mock_any_response(_scribed_poll_expectation())

        self._publish_user_voicemail_event()

        self._assert_mock_verified(
            self.calld_mock,
            {
                'method': 'GET',
                'path': f'/1.0/voicemails/{VOICEMAIL_ID}/messages/{MESSAGE_ID}/recording',
            },
        )
        self._assert_mock_verified(
            self.scribed_mock,
            {
                'method': 'POST',
                'path': '/transcriptions/jobs',
            },
        )
        self._assert_mock_verified(
            self.scribed_mock,
            {
                'method': 'GET',
                'path': '/transcriptions/jobs/1',
            },
        )

    def test_global_voicemail_event_triggers_transcription(self) -> None:
        self.calld_mock.mock_any_response(
            _calld_recording_expectation(VOICEMAIL_ID, MESSAGE_ID)
        )
        self.scribed_mock.mock_any_response(_scribed_job_creation_expectation())
        self.scribed_mock.mock_any_response(_scribed_poll_expectation())

        self._publish_global_voicemail_event()

        self._assert_mock_verified(
            self.calld_mock,
            {
                'method': 'GET',
                'path': f'/1.0/voicemails/{VOICEMAIL_ID}/messages/{MESSAGE_ID}/recording',
            },
        )
        self._assert_mock_verified(
            self.scribed_mock,
            {
                'method': 'POST',
                'path': '/transcriptions/jobs',
            },
        )
        self._assert_mock_verified(
            self.scribed_mock,
            {
                'method': 'GET',
                'path': '/transcriptions/jobs/1',
            },
        )

    def test_transcription_failure_does_not_crash(self) -> None:
        self.calld_mock.mock_any_response(
            _calld_recording_expectation(VOICEMAIL_ID, MESSAGE_ID)
        )
        self.scribed_mock.mock_any_response(_scribed_job_creation_expectation())
        self.scribed_mock.mock_any_response(_scribed_poll_expectation(status='failed'))

        self._publish_user_voicemail_event()

        self._assert_mock_verified(
            self.calld_mock,
            {
                'method': 'GET',
                'path': f'/1.0/voicemails/{VOICEMAIL_ID}/messages/{MESSAGE_ID}/recording',
            },
        )
        self._assert_mock_verified(
            self.scribed_mock,
            {
                'method': 'POST',
                'path': '/transcriptions/jobs',
            },
        )
        self._assert_mock_verified(
            self.scribed_mock,
            {
                'method': 'GET',
                'path': '/transcriptions/jobs/1',
            },
        )

        # Verify webhookd is still healthy
        def _webhookd_is_healthy():
            webhookd = self.make_webhookd(MASTER_TOKEN)
            status = webhookd.status.get()
            assert status['bus_consumer']['status'] == 'ok'

        until.assert_(_webhookd_is_healthy, timeout=REQUEST_TIMEOUT, interval=1)
