# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import requests

from .celery_tasks import _parse_countdown, poll_transcription_job

if TYPE_CHECKING:
    from wazo_calld_client import Client as CalldClient
    from wazo_confd_client import Client as ConfdClient

    from wazo_webhookd.types import WebhookdConfigDict

logger = logging.getLogger(__name__)

REQUEST_TIMEOUTS = 30


class VoicemailTranscriptionHandler:
    def __init__(
        self,
        config: WebhookdConfigDict,
        calld_client: CalldClient,
        confd_client: ConfdClient,
    ) -> None:
        self._config = config
        self._calld_client = calld_client
        self._confd_client = confd_client

    def _is_transcription_enabled(self, tenant_uuid: str) -> bool:
        result = self._confd_client.voicemail_transcription.get(tenant_uuid=tenant_uuid)
        return result['enabled']

    def _process_voicemail(
        self,
        voicemail_id: int,
        message_id: str,
        tenant_uuid: str,
    ) -> None:
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
            timeout=REQUEST_TIMEOUTS,
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
                'tenant_uuid': tenant_uuid,
            },
            countdown=countdown,
        )

    def _handle_voicemail_event(
        self, payload: dict[str, Any], headers: dict[str, Any]
    ) -> None:
        tenant_uuid = headers.get('tenant_uuid')
        if not tenant_uuid:
            logger.debug('Missing tenant_uuid in event headers, skipping transcription')
            return

        if not self._is_transcription_enabled(tenant_uuid):
            logger.debug(
                'Transcription not enabled for tenant %s, skipping', tenant_uuid
            )
            return

        data = payload.get('data', {})
        voicemail_id = data.get('voicemail_id')
        message_id = data.get('message_id')

        if not all([voicemail_id, message_id]):
            logger.warning(
                'Missing voicemail_id or message_id in event payload: %s', data
            )
            return

        self._process_voicemail(voicemail_id, message_id, tenant_uuid)

    def on_user_voicemail_created(
        self, payload: dict[str, Any], headers: dict[str, Any]
    ) -> None:
        self._handle_voicemail_event(payload, headers)

    def on_global_voicemail_created(
        self, payload: dict[str, Any], headers: dict[str, Any]
    ) -> None:
        self._handle_voicemail_event(payload, headers)
