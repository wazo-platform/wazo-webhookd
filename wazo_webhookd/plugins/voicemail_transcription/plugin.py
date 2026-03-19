# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from wazo_bus.resources.voicemail.event import (
    GlobalVoicemailMessageCreatedEvent,
    UserVoicemailMessageCreatedEvent,
)

from wazo_webhookd.plugins.voicemail_transcription.handler import (
    VoicemailTranscriptionHandler,
)

if TYPE_CHECKING:
    from wazo_webhookd.types import PluginDependencyDict

logger = logging.getLogger(__name__)


class Plugin:
    def load(self, dependencies: PluginDependencyDict) -> None:
        bus_consumer = dependencies['bus_consumer']
        config = dependencies['config']
        auth_client = dependencies['auth_client']

        handler = VoicemailTranscriptionHandler(config, auth_client)

        bus_consumer.subscribe(
            UserVoicemailMessageCreatedEvent.name,
            handler.on_user_voicemail_created,
        )
        bus_consumer.subscribe(
            GlobalVoicemailMessageCreatedEvent.name,
            handler.on_global_voicemail_created,
        )
