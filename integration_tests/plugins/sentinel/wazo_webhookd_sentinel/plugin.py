# Copyright 2017-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from collections import deque

from flask_restful import Resource

called = False
received: deque = deque(maxlen=1000)


def _queue_binding(bind_keys, binding):
    # the queue binding a subscription is consumed through: its own binding
    # without bind_keys, else the one it shares, keyed on the consumer's keys
    arguments = binding.arguments
    if bind_keys is not None:
        arguments = {'name': arguments['name'], 'x-match': 'all'} | {
            key: binding.arguments[key] for key in bind_keys if key in binding.arguments
        }
    return binding.routing_key, frozenset(arguments.items())


class SentinelResource(Resource):
    def __init__(self, bus_consumer):
        self._bus_consumer = bus_consumer

    def _get_bindings(self):
        consumer = self._bus_consumer
        bind_keys = getattr(consumer, '_ConsumerMixin__bind_keys', None)
        with consumer._ConsumerMixin__lock:
            subscriptions = {
                event: list(event_subscriptions)
                for event, event_subscriptions in consumer._ConsumerMixin__subscriptions.items()
            }
            queue = consumer._ConsumerMixin__queue
            live = {
                (binding.routing_key, frozenset(binding.arguments.items()))
                for binding in (queue.bindings if queue else ())
            }

        container = []
        for event, event_subscriptions in subscriptions.items():
            for _, binding in event_subscriptions:
                # only grab subscriptions of webhookd's subscription plugin
                if 'x-subscription' not in binding.arguments:
                    continue

                headers = binding.arguments.copy()
                uuid = headers.pop('x-subscription')
                headers.pop('name')
                container.append(
                    {
                        'uuid': uuid,
                        'event': event,
                        'headers': headers,
                        'bound': _queue_binding(bind_keys, binding) in live,
                    }
                )
        return container

    def get(self):
        return {
            'called': called,
            'bindings': self._get_bindings(),
            'received': list(received),
        }

    def post(self):
        global called
        called = True

    def delete(self):
        global called
        called = False
        received.clear()


class BusSentinelResource(Resource):
    _last_event_payload = None

    @classmethod
    def on_message(cls, body):
        if body['name'] == 'webhookd_ping':
            cls._last_event_payload = body['data']['payload']
        elif body['name'] == 'crash_ping':
            raise Exception('Crash message received')

    def get(self):
        return {'last_event_payload': self._last_event_payload}


class Plugin:
    def load(self, dependencies):
        api = dependencies['api']
        bus_consumer = dependencies['bus_consumer']
        api.add_resource(
            SentinelResource, '/sentinel', resource_class_args=[bus_consumer]
        )
        api.add_resource(BusSentinelResource, '/sentinel/bus')

        for event in ['webhookd_ping', 'crash_ping']:
            bus_consumer.subscribe(event, BusSentinelResource.on_message)

        # every message the queue delivers, before any dispatch: what the
        # broker routed to the queue, whatever the subscriptions do with it
        on_message_received = bus_consumer._ConsumerMixin__on_message_received

        def record_and_receive(body, message):
            received.append(dict(message.headers))
            return on_message_received(body, message)

        bus_consumer._ConsumerMixin__on_message_received = record_and_receive
