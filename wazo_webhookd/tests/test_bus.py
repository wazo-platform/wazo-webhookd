# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from unittest.mock import Mock

from wazo_webhookd.bus import BusConsumer

USER_UUID = 'd7a3f1b6-2a59-4f4c-9f5e-6f0f5bd2a1c4'


def connected_to(version: str) -> Mock:
    # the channel get_consumers receives: py-amqp keeps RabbitMQ's version in
    # the connection's start properties
    return Mock(connection=Mock(server_properties={'version': version}))


def dispatch(
    headers: dict | None, subscribed: dict, broker: Mock | None = None
) -> list:
    consumer = BusConsumer(
        name='test', exchange_name='wazo-headers', exchange_type='headers'
    )
    if broker is not None:
        consumer.get_consumers(Mock(), broker)
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

    def test_an_integer_matches_a_float_as_rabbitmq_before_3_13_does(self) -> None:
        # codex PRRT_kwDOBHUTtc63oNlU on wazo-bus#151: the broker's own
        # comparison, == up to 3.12, =:= from 3.13 on
        calls = dispatch(
            {'name': 'an-event', 'priority': 1.0},
            {'priority': 1},
            connected_to('3.10.8'),
        )

        assert len(calls) == 1

    def test_an_integer_does_not_match_a_float_on_rabbitmq_3_13_and_later(
        self,
    ) -> None:
        calls = dispatch(
            {'name': 'an-event', 'priority': 1.0},
            {'priority': 1},
            connected_to('4.0.5'),
        )

        assert calls == []
