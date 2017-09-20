# Copyright (C) 2015-2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

from flask.ext.restful import Resource

called = False


class SentinelResource(Resource):

    def get(self):
        return {'called': called}

    def post(self):
        global called
        called = True


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        api.add_resource(SentinelResource, '/sentinel')
