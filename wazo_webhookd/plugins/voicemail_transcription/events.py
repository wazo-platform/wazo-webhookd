# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from wazo_bus.resources.common.event import ServiceEvent


class VoicemailTranscriptionFinishedEvent(ServiceEvent):
    name = 'voicemail_transcription_completed'
    routing_key_fmt = 'voicemail.transcription.completed'
