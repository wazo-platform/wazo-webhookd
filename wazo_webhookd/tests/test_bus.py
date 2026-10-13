# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

from wazo_webhookd.bus import WebhookdExchange

THREAD_COUNT = 5


class ConcurrencyRecorder:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active = 0
        self.max_active = 0

    def exchange_bind(self, *args, **kwargs) -> None:
        with self._lock:
            self._active += 1
            self.max_active = max(self.max_active, self._active)
        time.sleep(0.05)
        with self._lock:
            self._active -= 1


class TestWebhookdExchange:
    def test_subscribe_connected_serializes_connection_usage(self) -> None:
        recorder = ConcurrencyRecorder()
        consumer_connection = MagicMock()
        cloned_connection = consumer_connection.clone.return_value
        cloned_connection.default_channel.exchange_bind = recorder.exchange_bind
        exchange = WebhookdExchange(
            'wazo-webhookd', 'headers', {'auto_delete': True}, 'wazo-headers', 'headers'
        )
        start = threading.Barrier(THREAD_COUNT)

        def subscribe(event_name: str) -> None:
            start.wait()
            exchange.subscribe_connected(event_name, consumer_connection)

        threads = [
            threading.Thread(target=subscribe, args=(f'event_{i}',))
            for i in range(THREAD_COUNT)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert recorder.max_active == 1
        consumer_connection.clone.assert_called_once_with()
