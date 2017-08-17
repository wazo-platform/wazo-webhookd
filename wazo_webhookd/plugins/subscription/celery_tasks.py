# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import requests


def load(celery_app):

    @celery_app.task
    def http_callback(options):
        body = options.get('body')
        if body:
            body = body.encode('utf-8')
        verify = options.get('verify_certificate')
        if verify:
            verify = True if verify == 'true' else verify
            verify = False if verify == 'false' else verify

        requests.request(options['method'],
                         options['url'],
                         data=body,
                         verify=verify)
