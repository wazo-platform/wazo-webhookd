# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import Any
from uuid import uuid4

from wazo_webhookd.bus import BusConsumer


class TestDeprecatedSubscription:
    def setup_method(self) -> None:
        self.consumer = BusConsumer(
            name='wazo_webhookd',
            exchange_name='wazo-headers',
            exchange_type='headers',
        )
        self.received: list[tuple[dict, Any]] = []

    def callback(self, payload: dict, headers: Any) -> None:
        self.received.append((payload, headers))

    def test_unsubscribe_removes_the_subscribed_callback(self) -> None:
        uuid = str(uuid4())
        self.consumer.subscribe_to_event_names(
            uuid, ['some_event'], '', '', self.callback
        )

        self.consumer.unsubscribe_from_event_names(uuid)

        assert self.consumer._ConsumerMixin__subscriptions == {}

    def test_callback_receives_the_payload(self) -> None:
        self.consumer.subscribe_to_event_names(
            str(uuid4()), ['some_event'], '', '', self.callback
        )
        payload = {'name': 'some_event', 'data': {}}

        self.consumer._ConsumerMixin__dispatch(
            'some_event', payload, {'name': 'some_event'}
        )

        assert [received for received, _ in self.received] == [payload]
