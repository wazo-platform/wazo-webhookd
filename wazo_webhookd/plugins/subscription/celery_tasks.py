# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import requests


def load(celery_app):

    @celery_app.task
    def http_callback(method, url, body):
        if body:
            body = body.encode('utf-8')
        requests.request(method, url, data=body)
