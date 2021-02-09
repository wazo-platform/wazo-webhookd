# Copyright 2017-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from flask_restful import Resource

called = False


class SentinelResource(Resource):
    def __init__(self, bus_consumer):
        self._bus_consumer = bus_consumer

    def get(self):
        # NOTE(sileht): returns only uuid in sync with the database
        consumers = list(
            set(self._bus_consumer._consumers.keys())
            - set([uuid for uuid, _ in self._bus_consumer._updated_consumers])
        )
        return {'called': called, 'consumers': consumers}

    def post(self):
        global called
        called = True

    def delete(self):
        global called
        called = False


class BusSentinelResource(Resource):
    _last_event_payload = None

    @classmethod
    def on_message(cls, body, message):
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
        bus_consumer.subscribe_to_event_names(
            'sentinel-subscription',
            ['webhookd_ping', 'crash_ping'],
            user_uuid=None,
            wazo_uuid=None,
            callback=BusSentinelResource.on_message,
        )
