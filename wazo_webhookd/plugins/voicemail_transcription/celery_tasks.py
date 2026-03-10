# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from celery import Task

from wazo_webhookd.celery import app

from .services import (
    fetch_voicemail_recording,
    get_auth_token,
    get_transcription_result,
    submit_transcription_job,
    user_has_uc_license,
)

if TYPE_CHECKING:
    from ...types import WebhookdConfigDict

logger = logging.getLogger(__name__)


@app.task(bind=True)
def transcribe_voicemail_task(
    task: Task,
    config: WebhookdConfigDict,
    voicemail_id: int,
    message_id: str,
    user_uuid: str | None = None,
    require_license_check: bool = True,
    job_id: str | None = None,
) -> None:
    transcription_config = config.get('voicemail_transcription', {})
    service_url = transcription_config.get('service_url')
    max_poll_attempts = transcription_config.get('max_poll_attempts', 10)

    if not service_url:
        logger.error('Transcription service_url is not configured, skipping')
        return

    task.max_retries = max_poll_attempts

    token = get_auth_token(config['auth'])

    # License check for user voicemails
    if require_license_check and user_uuid:
        confd_config = config.get('confd', {})
        if not user_has_uc_license(confd_config, user_uuid, token):
            logger.info(
                'User %s does not have UC license, skipping transcription',
                user_uuid,
            )
            return

    # If we already have a job_id, we're polling for the result
    if job_id:
        result = get_transcription_result(service_url, job_id)
        status = result.get('status')

        if status == 'completed':
            logger.info(
                'Transcription completed for voicemail %s, message %s',
                voicemail_id,
                message_id,
            )
            return

        if status == 'error':
            logger.error(
                'Transcription failed for voicemail %s, message %s: %s',
                voicemail_id,
                message_id,
                result.get('error'),
            )
            return

        # Still in progress, retry with estimated_completion_at
        estimated_completion_at = result.get('estimated_completion_at')
        countdown = _parse_countdown(estimated_completion_at)
        logger.debug(
            'Transcription job %s still in progress, retrying in %s seconds',
            job_id,
            countdown,
        )
        raise task.retry(
            kwargs={
                'config': config,
                'voicemail_id': voicemail_id,
                'message_id': message_id,
                'user_uuid': user_uuid,
                'require_license_check': False,
                'job_id': job_id,
            },
            countdown=countdown,
        )

    # Fetch audio and submit transcription job
    calld_config = config.get('calld', {})
    audio_data = fetch_voicemail_recording(
        calld_config, voicemail_id, message_id, token
    )
    logger.debug(
        'Fetched %d bytes of audio for voicemail %s, message %s',
        len(audio_data),
        voicemail_id,
        message_id,
    )

    job_id = submit_transcription_job(service_url, audio_data)
    logger.info(
        'Submitted transcription job %s for voicemail %s, message %s',
        job_id,
        voicemail_id,
        message_id,
    )

    # Start polling for the result
    raise task.retry(
        kwargs={
            'config': config,
            'voicemail_id': voicemail_id,
            'message_id': message_id,
            'user_uuid': user_uuid,
            'require_license_check': False,
            'job_id': job_id,
        },
        countdown=5,
    )


def _parse_countdown(estimated_completion_at: str | None) -> int:
    if not estimated_completion_at:
        return 5

    from datetime import datetime, timezone

    try:
        estimated = datetime.fromisoformat(estimated_completion_at)
        now = datetime.now(tz=timezone.utc)
        delta = (estimated - now).total_seconds()
        return max(int(delta), 1)
    except (ValueError, TypeError):
        return 5
