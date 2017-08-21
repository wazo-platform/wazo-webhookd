# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import requests

from jinja2 import Environment


def load(celery_app):

    @celery_app.task
    def http_callback(options, event):
        headers = {}

        body = options.get('body')
        if body:
            template = body
            values = {
                'event_name': event['name'],
                'event': event['data'],
                'wazo_uuid': event['origin_uuid'],
            }
            body = Environment().from_string(template).render(values)
            body = body.encode('utf-8')

        verify = options.get('verify_certificate')
        if verify:
            verify = True if verify == 'true' else verify
            verify = False if verify == 'false' else verify

        content_type = options.get('content_type')
        if content_type:
            headers['Content-Type'] = content_type

        requests.request(options['method'],
                         options['url'],
                         data=body,
                         verify=verify,
                         headers=headers)
