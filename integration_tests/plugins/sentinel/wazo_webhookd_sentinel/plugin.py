# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
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
        return {"called": called, "consumers": consumers}

    def post(self):
        global called
        called = True

    def delete(self):
        global called
        called = False


class Plugin(object):
    def load(self, dependencies):
        api = dependencies["api"]
        bus_consumer = dependencies["bus_consumer"]
        api.add_resource(
            SentinelResource, "/sentinel", resource_class_args=[bus_consumer]
        )
