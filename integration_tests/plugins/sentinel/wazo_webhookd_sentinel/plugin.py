# Copyright 2017-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from uuid import uuid4

from flask_restful import Resource

called = False


class SentinelResource(Resource):
    def __init__(self, bus_consumer):
        self._bus_consumer = bus_consumer

    def _get_bindings(self):
        container = []
        for binding in self._bus_consumer._ConsumerMixin__queue.bindings:
            # only grab bindings from subscriptions
            if 'x-subscription' not in binding.arguments:
                continue

            headers = binding.arguments.copy()
            uuid = headers.pop('x-subscription')
            event = headers.pop('name')
            container.append({'uuid': uuid, 'event': event, 'headers': headers})
        return container

    def get(self):
        return {'called': called, 'bindings': self._get_bindings()}

    def post(self):
        global called
        called = True

    def delete(self):
        global called
        called = False


class BusSentinelResource(Resource):
    _last_event_payload = None

    @classmethod
    def on_message(cls, body):
        if body['name'] == 'webhookd_ping':
            cls._last_event_payload = body['data']['payload']
        elif body['name'] == 'crash_ping':
            raise Exception('Crash message received')

    @classmethod
    def deprecated_on_message(cls, body, message):
        if body['name'] == 'webhookd_deprecated_ping':
            cls._last_event_payload = body['data']['payload']

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

        # compatibility test for deprecated bus api
        bus_consumer.subscribe_to_event_names(
            uuid4(),
            ['webhookd_deprecated_ping'],
            None,
            None,
            BusSentinelResource.deprecated_on_message,
        )
