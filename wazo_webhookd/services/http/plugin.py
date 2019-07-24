# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import logging
import requests
import socket
import urllib.parse

from jinja2 import Environment

from wazo_webhookd.services.helpers import (
    requests_automatic_hook_retry,
    requests_automatic_detail,
)

logger = logging.getLogger(__name__)

REQUESTS_TIMEOUT = (5, 15)  # seconds


class Service:
    def load(self, dependencies):
        pass

    @classmethod
    def run(cls, task, config, subscription, event):
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

        if subscription['owner_user_uuid'] and cls.url_is_localhost(url):
            # some services only listen on 127.0.0.1 and should not be accessible to users
            logger.warning(
                'Rejecting callback from user "%s" to url "%s": remote host is localhost!',
                subscription['owner_user_uuid'],
                url,
            )
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

        with requests_automatic_hook_retry(task):
            with requests.request(
                options['method'],
                url,
                data=body,
                verify=verify,
                headers=headers,
                timeout=REQUESTS_TIMEOUT,
            ) as r:
                r.raise_for_status()
                return requests_automatic_detail(r)

    @staticmethod
    def url_is_localhost(url):
        remote_host = urllib.parse.urlparse(url).hostname
        remote_address = socket.gethostbyname(remote_host)
        return remote_address == '127.0.0.1'
