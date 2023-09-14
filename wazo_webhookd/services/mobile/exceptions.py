# Copyright 2020-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from typing import Any

from wazo_webhookd.services.helpers import HookExpectedError


class NotificationError(HookExpectedError):
    def __init__(self, details: dict[str, Any]) -> None:
        details.setdefault('error_id', 'notification-error')
        super().__init__(details)
