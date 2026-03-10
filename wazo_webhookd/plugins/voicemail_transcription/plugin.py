# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from .handler import VoicemailTranscriptionHandler

if TYPE_CHECKING:
    from ...types import PluginDependencyDict


class Plugin:
    def load(self, dependencies: PluginDependencyDict) -> None:
        bus_consumer = dependencies['bus_consumer']
        config = dependencies['config']

        handler = VoicemailTranscriptionHandler(config)

        bus_consumer.subscribe(
            'user_voicemail_message_created',
            handler.on_user_voicemail_created,
            headers={'x-internal': True},
        )
        bus_consumer.subscribe(
            'global_voicemail_message_created',
            handler.on_global_voicemail_created,
            headers={'x-internal': True},
        )
