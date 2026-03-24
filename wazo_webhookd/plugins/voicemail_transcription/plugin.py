# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from wazo_bus.resources.voicemail.event import (
    GlobalVoicemailMessageCreatedEvent,
    UserVoicemailMessageCreatedEvent,
)
from wazo_calld_client import Client as CalldClient
from wazo_confd_client import Client as ConfdClient

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
        next_token_change_subscribe = dependencies['next_token_change_subscribe']

        calld_client = CalldClient(**config['calld'])
        next_token_change_subscribe(calld_client.set_token)

        confd_client = ConfdClient(**config['confd'])
        next_token_change_subscribe(confd_client.set_token)

        handler = VoicemailTranscriptionHandler(config, calld_client, confd_client)

        bus_consumer.subscribe(
            UserVoicemailMessageCreatedEvent.name,
            handler.on_user_voicemail_created,
        )
        bus_consumer.subscribe(
            GlobalVoicemailMessageCreatedEvent.name,
            handler.on_global_voicemail_created,
        )
