# Copyright 2022-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging


class TeamsLogAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return f'[MS Teams Integration] {msg}', kwargs
