# Copyright 2020-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import logging
import threading
from typing import cast, TYPE_CHECKING

if TYPE_CHECKING:
    from ...types import WebhookdConfigDict


class ConfigService:
    # Changing root logger log-level requires application-wide lock.
    # This lock will be shared across all instances.
    _lock = threading.Lock()

    def __init__(self, config: WebhookdConfigDict) -> None:
        self._config: WebhookdConfigDict = cast(WebhookdConfigDict, dict(config))
        self._enabled = False

    def get_config(self) -> WebhookdConfigDict:
        with self._lock:
            return cast(WebhookdConfigDict, dict(self._config))

    def update_config(self, config: WebhookdConfigDict) -> None:
        with self._lock:
            self._update_debug(config['debug'])
            self._config['debug'] = config['debug']

    def _update_debug(self, debug: bool) -> None:
        if debug:
            self._enable_debug()
        else:
            self._disable_debug()

    def _enable_debug(self) -> None:
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

    def _disable_debug(self) -> None:
        root_logger = logging.getLogger()
        root_logger.setLevel(self._config['log_level'])
