# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from wazo_webhookd.bus import BusConsumer

USER_UUID = 'd7a3f1b6-2a59-4f4c-9f5e-6f0f5bd2a1c4'


def dispatch(headers: dict | None, subscribed: dict) -> list:
    consumer = BusConsumer(
        name='test', exchange_name='wazo-headers', exchange_type='headers'
    )
    received: list = []

    def handler(payload: dict) -> None:
        received.append(payload)

    consumer.subscribe('an-event', handler, headers=subscribed)
    consumer._ConsumerMixin__dispatch('an-event', {'data': 1}, headers)
    return received


class TestDispatchComparesHeadersAsRabbitMQ:
    def test_a_boolean_subscription_does_not_receive_an_integer_header(self) -> None:
        subscribed = {f'user_uuid:{USER_UUID}': True}

        calls = dispatch({'name': 'an-event', f'user_uuid:{USER_UUID}': 1}, subscribed)

        assert calls == []

    def test_a_boolean_subscription_receives_its_boolean_header(self) -> None:
        subscribed = {f'user_uuid:{USER_UUID}': True}

        calls = dispatch(
            {'name': 'an-event', f'user_uuid:{USER_UUID}': True}, subscribed
        )

        assert len(calls) == 1

    def test_a_text_subscription_receives_the_same_text_as_bytes(self) -> None:
        calls = dispatch(
            {'name': 'an-event', 'tenant_uuid': b't1'}, {'tenant_uuid': 't1'}
        )

        assert len(calls) == 1

    def test_a_message_without_headers_reaches_no_header_subscription(self) -> None:
        calls = dispatch(None, {'tenant_uuid': 't1'})

        assert calls == []
