# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import cgi
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

        url = Environment().from_string(options['url']).render(values)

        if subscription['owner_user_uuid'] and cls.url_is_localhost(url):
            # some services only listen on 127.0.0.1 and should not be accessible to users
            logger.warning(
                'Rejecting callback from user "%s" to url "%s": remote host is localhost!',
                subscription['owner_user_uuid'],
                url,
            )
            return

        body = options.get('body')

        if body:
            content_type = options.get('content_type', 'text/plain')
            # NOTE(sileht): parse_header will drop any erroneous options
            ct_mimetype, ct_options = cgi.parse_header(content_type)
            ct_options.setdefault('charset', 'utf-8')
            data = Environment().from_string(body).render(values)
        else:
            ct_mimetype = 'application/json'
            ct_options = {'charset': 'utf-8'}
            data = json.dumps(event['data'])

        data = data.encode(ct_options['charset'])

        headers['Content-Type'] = "{}; {}".format(
            ct_mimetype, "; ".join(map("=".join, ct_options.items()))
        )

        verify = options.get('verify_certificate')
        if verify:
            verify = True if verify == 'true' else verify
            verify = False if verify == 'false' else verify

        with requests_automatic_hook_retry(task):
            session = requests.Session()
            session.trust_env = False
            with session.request(
                options['method'],
                url,
                data=data,
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
