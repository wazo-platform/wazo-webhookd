# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import requests
from wazo_calld_client import Client as CalldClient

from wazo_webhookd.plugins.voicemail_transcription.celery_tasks import (
    _parse_countdown,
    poll_transcription_job,
)

if TYPE_CHECKING:
    from wazo_auth_client.client import AuthClient

    from wazo_webhookd.types import WebhookdConfigDict

logger = logging.getLogger(__name__)


class VoicemailTranscriptionHandler:
    def __init__(self, config: WebhookdConfigDict, auth_client: AuthClient) -> None:
        self._config = config
        self._auth_client = auth_client
        self._calld_client = CalldClient(**config['calld'])

    def _set_calld_token(self) -> None:
        token = self._auth_client.token.new()
        self._calld_client.set_token(token['token'])

    def _process_voicemail(self, voicemail_id: int, message_id: str) -> None:
        self._set_calld_token()
        recording = self._calld_client.voicemails.get_voicemail_recording(
            voicemail_id, message_id
        )
        logger.debug(
            'Fetched recording for voicemail %s message %s (%d bytes)',
            voicemail_id,
            message_id,
            len(recording),
        )

        service_url = self._config['voicemail_transcription']['service_url']
        url = f'{service_url}/transcriptions/jobs'
        response = requests.post(
            url,
            files={'audio': ('voicemail.wav', recording, 'audio/wav')},
        )
        response.raise_for_status()
        result = response.json()
        job_id = result['job_id']
        logger.info(
            'Submitted transcription job %s for voicemail %s message %s',
            job_id,
            voicemail_id,
            message_id,
        )

        countdown = _parse_countdown(result.get('estimated_completion_at'))
        poll_transcription_job.apply_async(
            kwargs={
                'config': dict(self._config),
                'service_url': service_url,
                'job_id': job_id,
                'voicemail_id': voicemail_id,
                'message_id': message_id,
            },
            countdown=countdown,
        )

    def on_user_voicemail_created(self, payload: dict[str, Any]) -> None:
        data = payload.get('data', {})
        voicemail_id = data.get('voicemail_id')
        message_id = data.get('message_id')

        if not all([voicemail_id, message_id]):
            logger.warning(
                'Missing voicemail_id or message_id in event payload: %s', data
            )
            return

        self._process_voicemail(voicemail_id, message_id)

    def on_global_voicemail_created(self, payload: dict[str, Any]) -> None:
        data = payload.get('data', {})
        voicemail_id = data.get('voicemail_id')
        message_id = data.get('message_id')

        if not all([voicemail_id, message_id]):
            logger.warning(
                'Missing voicemail_id or message_id in event payload: %s', data
            )
            return

        self._process_voicemail(voicemail_id, message_id)
