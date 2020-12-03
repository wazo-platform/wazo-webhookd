# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import threading


class ConfigService:

    # share the lock between service instances
    _lock = threading.Lock()

    def __init__(self, config):
        self._config = config
        self._enabled = False
        self._lock = threading.Lock()

    def get_runtime_debug(self):
        with self._lock:
            return self._enabled

    def enable_runtime_debug(self):
        with self._lock:
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.DEBUG)
            self._enabled = True

    def disable_runtime_debug(self):
        with self._lock:
            root_logger = logging.getLogger()
            root_logger.setLevel(self._config['log_level'])
            self._enabled = False
