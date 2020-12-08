# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import threading


class ConfigService:

    # share the lock between service instances
    _lock = threading.Lock()

    def __init__(self, config):
        self._config = dict(config)
        self._enabled = False
        self._lock = threading.Lock()

    def get_config(self):
        with self._lock:
            return dict(self._config)

    def update_config(self, config):
        with self._lock:
            self._update_debug(config['debug'])
            self._config['debug'] = config['debug']

    def _update_debug(self, debug):
        if debug:
            self._enable_debug()
        else:
            self._disable_debug()

    def _enable_debug(self):
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

    def _disable_debug(self):
        root_logger = logging.getLogger()
        root_logger.setLevel(self._config['log_level'])
