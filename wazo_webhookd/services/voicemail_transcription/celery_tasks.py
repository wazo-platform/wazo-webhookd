# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import requests
from celery import Task
from wazo_bus.resources.voicemail_transcription.event import (
    VoicemailTranscriptionCompletedEvent,
)
from wazo_bus.resources.voicemail_transcription.types import (
    TranscriptionCompletedPayload,
)

from wazo_webhookd.bus import BusPublisher
from wazo_webhookd.celery import app

if TYPE_CHECKING:
    from wazo_webhookd.types import WebhookdConfigDict

logger = logging.getLogger(__name__)

DEFAULT_POLL_COUNTDOWN = 5
DEFAULT_POLL_ATTEMPTS = 10
REQUEST_TIMEOUTS = 30


def _parse_countdown(estimated_completion_at: str | None) -> int:
    if not estimated_completion_at:
        return DEFAULT_POLL_COUNTDOWN

    try:
        estimated = datetime.fromisoformat(estimated_completion_at)
        now = datetime.now(tz=timezone.utc)
        delta = (estimated - now).total_seconds()
        return max(int(delta), 1)
    except (ValueError, TypeError):
        logger.warning(
            f'Failed to parse the estimated completion time, got {estimated_completion_at}'
        )
        logger.warning(f'Defaulting to {DEFAULT_POLL_COUNTDOWN}')
        return DEFAULT_POLL_COUNTDOWN


def _build_transcription_data(
    result: dict,
    voicemail_id: int,
    message_id: str,
    tenant_uuid: str,
) -> TranscriptionCompletedPayload:
    item = result['transcriptions_items'][0]
    transcription = item['transcription']
    return TranscriptionCompletedPayload(
        message_id=message_id,
        tenant_uuid=tenant_uuid,
        voicemail_id=voicemail_id,
        transcription_text=transcription['text'],
        provider_id=transcription['provider_id'],
        language=transcription['language'],
        duration=transcription['duration'],
        completed_at=item['completed_at'],
    )


@app.task(bind=True)
def poll_transcription_job(
    self: Task,
    config: WebhookdConfigDict,
    service_url: str,
    job_id: str,
    voicemail_id: int,
    message_id: str,
    tenant_uuid: str,
) -> None:
    max_poll_attempts = config['voicemail_transcription'].get(
        'max_poll_attempts', DEFAULT_POLL_ATTEMPTS
    )
    self.max_retries = max_poll_attempts - 1

    url = f'{service_url}/transcriptions/jobs/{job_id}'
    response = requests.get(url, timeout=REQUEST_TIMEOUTS)
    response.raise_for_status()
    result = response.json()
    status = result.get('status')

    if status == 'completed':
        logger.info(
            'Transcription job %s completed for voicemail %s message %s',
            job_id,
            voicemail_id,
            message_id,
        )
        transcription = _build_transcription_data(
            result, voicemail_id, message_id, tenant_uuid
        )
        with BusPublisher.from_config(config['uuid'], config['bus']) as bus_publisher:
            event = VoicemailTranscriptionCompletedEvent(transcription, tenant_uuid)
            bus_publisher.publish(event)
            return

    if status == 'failed':
        logger.error(
            'Transcription job %s failed for voicemail %s message %s: %s',
            job_id,
            voicemail_id,
            message_id,
            result.get('error'),
        )
        return

    estimated_completion_at = result.get('estimated_completion_at')
    countdown = _parse_countdown(estimated_completion_at)
    logger.debug(
        'Transcription job %s still pending, retrying in %s seconds',
        job_id,
        countdown,
    )
    raise self.retry(
        kwargs={
            'config': config,
            'service_url': service_url,
            'job_id': job_id,
            'voicemail_id': voicemail_id,
            'message_id': message_id,
            'tenant_uuid': tenant_uuid,
        },
        countdown=countdown,
    )
