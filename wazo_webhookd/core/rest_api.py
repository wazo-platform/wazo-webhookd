# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging
import os

from cheroot import wsgi
from datetime import timedelta
from flask import Flask, request
from flask_restful import Api
from flask_restful import Resource
from flask_cors import CORS
from xivo.auth_verifier import AuthVerifier
from xivo import http_helpers
from xivo import mallow_helpers
from xivo import rest_api_helpers

VERSION = 1.0

logger = logging.getLogger(__name__)
app = Flask('xivo_ctid_ng')
api = Api(app, prefix='/{}'.format(VERSION))
auth_verifier = AuthVerifier()


def log_request_params(response):
    http_helpers.log_request_hide_token(response)
    logger.debug('request data: %s', request.data or '""')
    logger.debug('response body: %s', response.data.strip() if response.data else '""')
    return response


class CoreRestApi(object):

    def __init__(self, global_config):
        self.config = global_config['rest_api']
        http_helpers.add_logger(app, logger)
        app.after_request(log_request_params)
        app.secret_key = os.urandom(24)
        app.permanent_session_lifetime = timedelta(minutes=5)
        auth_verifier.set_config(global_config['auth'])
        self._load_cors()
        self.server = None

    def _load_cors(self):
        cors_config = dict(self.config.get('cors', {}))
        enabled = cors_config.pop('enabled', False)
        if enabled:
            CORS(app, **cors_config)

    def run(self):
        bind_addr = (self.config['listen'], self.config['port'])

        wsgi_app = wsgi.WSGIPathInfoDispatcher({'/': app})
        self.server = wsgi.WSGIServer(bind_addr=bind_addr,
                                      wsgi_app=wsgi_app)
        self.server.ssl_adapter = http_helpers.ssl_adapter(self.config['certificate'],
                                                           self.config['private_key'])
        logger.debug('WSGIServer starting... uid: %s, listen: %s:%s', os.getuid(), bind_addr[0], bind_addr[1])
        for route in http_helpers.list_routes(app):
            logger.debug(route)

        try:
            self.server.start()
        except KeyboardInterrupt:
            self.server.stop()

    def stop(self):
        if self.server:
            self.server.stop()


class ErrorCatchingResource(Resource):
    method_decorators = ([mallow_helpers.handle_validation_exception,
                          rest_api_helpers.handle_api_exception] +
                         Resource.method_decorators)


class AuthResource(ErrorCatchingResource):
    method_decorators = [auth_verifier.verify_token] + ErrorCatchingResource.method_decorators
