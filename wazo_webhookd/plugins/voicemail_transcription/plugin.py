# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from wazo_bus.resources.voicemail.event import (
    GlobalVoicemailMessageCreatedEvent,
    UserVoicemailMessageCreatedEvent,
)

if TYPE_CHECKING:
    from wazo_webhookd.bus import BusConsumer
    from wazo_webhookd.types import PluginDependencyDict

logger = logging.getLogger(__name__)


class Plugin:
    _bus_consumer: BusConsumer

    def load(self, dependencies: PluginDependencyDict) -> None:
        self._bus_consumer = dependencies['bus_consumer']
        self._bus_consumer.subscribe(
            UserVoicemailMessageCreatedEvent.name,
            self._on_user_voicemail_created,
        )
        self._bus_consumer.subscribe(
            GlobalVoicemailMessageCreatedEvent.name,
            self._on_global_voicemail_created,
        )

    def _on_user_voicemail_created(self, event: dict[str, Any]) -> None:
        logger.debug('Received user voicemail created event: %s', event)

    def _on_global_voicemail_created(self, event: dict[str, Any]) -> None:
        logger.debug('Received global voicemail created event: %s', event)
