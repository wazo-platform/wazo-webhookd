# Copyright 2017-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from flask_restful import Resource

called = False


class SentinelResource(Resource):

    def get(self):
        return {'called': called}

    def post(self):
        global called
        called = True

    def delete(self):
        global called
        called = False


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        api.add_resource(SentinelResource, '/sentinel')
