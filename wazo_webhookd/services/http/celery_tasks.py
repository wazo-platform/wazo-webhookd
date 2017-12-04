# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import json
import logging
import requests
import socket
import urllib.parse

from jinja2 import Environment

logger = logging.getLogger(__name__)


def load(celery_app):

    @celery_app.task
    def http_callback(subscription, event):
        options = subscription['config']
        headers = {}
        values = {
            'event_name': event['name'],
            'event': event['data'],
            'wazo_uuid': event['origin_uuid'],
        }

        url = options['url']
        template = url
        url = Environment().from_string(template).render(values)

        if subscription['owner_user_uuid'] and url_is_localhost(url):
            # some services only listen on 127.0.0.1 and should not be accessible to users
            logger.warning('Rejecting callback from user "%s" to url "%s": remote host is localhost!',
                           subscription['owner_user_uuid'],
                           url)
            return

        content_type = options.get('content_type')

        body = options.get('body')
        if body:
            template = body
            body = Environment().from_string(template).render(values)
            body = body.encode('utf-8')
        else:
            body = json.dumps(event['data'])
            content_type = 'application/json'

        if content_type:
            headers['Content-Type'] = content_type

        verify = options.get('verify_certificate')
        if verify:
            verify = True if verify == 'true' else verify
            verify = False if verify == 'false' else verify

        requests.request(options['method'],
                         url,
                         data=body,
                         verify=verify,
                         headers=headers)

    return http_callback


def url_is_localhost(url):
    remote_host = urllib.parse.urlparse(url).hostname
    remote_address = socket.gethostbyname(remote_host)
    return remote_address == '127.0.0.1'
