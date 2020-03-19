# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_webhookd.services.helpers import HookExpectedError


class NotificationError(HookExpectedError):
    def __init__(self, details):
        details.setdefault('error_id', 'notification-error')
        super().__init__(details)
