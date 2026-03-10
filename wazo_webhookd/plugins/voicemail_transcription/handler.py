# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .celery_tasks import transcribe_voicemail_task

if TYPE_CHECKING:
    from ...types import WebhookdConfigDict

logger = logging.getLogger(__name__)


class VoicemailTranscriptionHandler:
    def __init__(self, config: WebhookdConfigDict) -> None:
        self._config = config

    def on_user_voicemail_created(
        self, payload: dict[str, Any], headers: dict[str, Any]
    ) -> None:
        data = payload.get('data', {})
        voicemail_id = data.get('voicemail_id')
        message_id = data.get('message_id')
        user_uuid = data.get('user_uuid')

        if not all([voicemail_id, message_id, user_uuid]):
            logger.warning(
                'Incomplete voicemail event data, skipping transcription: %s', data
            )
            return

        logger.debug(
            'User voicemail created for user %s, voicemail %s, message %s',
            user_uuid,
            voicemail_id,
            message_id,
        )

        transcribe_voicemail_task.delay(
            dict(self._config),
            voicemail_id,
            message_id,
            user_uuid=user_uuid,
            require_license_check=True,
        )

    def on_global_voicemail_created(
        self, payload: dict[str, Any], headers: dict[str, Any]
    ) -> None:
        data = payload.get('data', {})
        voicemail_id = data.get('voicemail_id')
        message_id = data.get('message_id')

        if not all([voicemail_id, message_id]):
            logger.warning(
                'Incomplete voicemail event data, skipping transcription: %s', data
            )
            return

        logger.debug(
            'Global voicemail created for voicemail %s, message %s',
            voicemail_id,
            message_id,
        )

        transcribe_voicemail_task.delay(
            dict(self._config),
            voicemail_id,
            message_id,
            user_uuid=None,
            require_license_check=False,
        )
