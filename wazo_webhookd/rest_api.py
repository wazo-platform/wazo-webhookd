# Copyright 2017-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import logging
import os
from datetime import timedelta

from cheroot import wsgi
from flask import Flask, Response, request
from flask_cors import CORS
from flask_restful import Api, Resource
from xivo import http_helpers, mallow_helpers, rest_api_helpers
from xivo.flask.auth_verifier import AuthVerifierFlask

from wazo_webhookd.types import WebhookdConfigDict

VERSION = 1.0

logger = logging.getLogger(__name__)
app = Flask('wazo-webhookd')
api = Api(app, prefix=f'/{VERSION}')
auth_verifier = AuthVerifierFlask()


def log_request_params(response: Response) -> Response:
    http_helpers.log_request_hide_token(response)
    logger.debug('request data: %s', request.data or '""')
    logger.debug('response body: %s', response.data.strip() if response.data else '""')
    return response


class CoreRestApi:
    def __init__(self, global_config: WebhookdConfigDict) -> None:
        self.config = global_config['rest_api']
        http_helpers.add_logger(app, logger)
        app.after_request(log_request_params)
        app.secret_key = os.urandom(24)
        app.permanent_session_lifetime = timedelta(minutes=5)
        app.config['auth'] = global_config['auth']
        self._load_cors()
        self.server: wsgi.WSGIServer = None  # type: ignore[assignment]

    def _load_cors(self) -> None:
        cors_config = dict(self.config.get('cors', {}))
        if cors_config.pop('enabled', False):
            CORS(app, **cors_config)

    def run(self) -> None:
        bind_addr = (self.config['listen'], self.config['port'])

        wsgi_app = wsgi.WSGIPathInfoDispatcher({'/': app})
        self.server = wsgi.WSGIServer(
            bind_addr=bind_addr,
            wsgi_app=wsgi_app,
            numthreads=self.config['max_threads'],
        )
        if self.config['certificate'] and self.config['private_key']:
            logger.warning(
                'Using service SSL configuration is deprecated. Please use NGINX instead.'
            )
            self.server.ssl_adapter = http_helpers.ssl_adapter(  # type: ignore
                self.config['certificate'], self.config['private_key']
            )
        logger.debug(
            'WSGIServer starting... uid: %s, listen: %s:%s',
            os.getuid(),
            bind_addr[0],
            bind_addr[1],
        )
        for route in http_helpers.list_routes(app):
            logger.debug(route)

        self.server.start()

    def stop(self) -> None:
        if self.server:
            self.server.stop()


class ErrorCatchingResource(Resource):
    method_decorators = [
        mallow_helpers.handle_validation_exception,
        rest_api_helpers.handle_api_exception,
    ] + Resource.method_decorators


class AuthResource(ErrorCatchingResource):
    method_decorators = [
        auth_verifier.verify_tenant,
        auth_verifier.verify_token,
    ] + ErrorCatchingResource.method_decorators
