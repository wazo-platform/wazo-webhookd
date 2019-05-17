# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import logging
import random
import requests
import socket
import urllib.parse

from jinja2 import Environment

logger = logging.getLogger(__name__)

# TODO(sileht): should be configurable, but we don't pass configuration to
# webhookd plugin yet
MAX_RETRIES = 20
REQUESTS_TIMEOUT = 5  # seconds


def load(celery_app):
    @celery_app.task(bind=True, max_retries=MAX_RETRIES)
    def http_callback(self, subscription, event):
        options = subscription["config"]
        headers = {}
        values = {
            "event_name": event["name"],
            "event": event["data"],
            "wazo_uuid": event["origin_uuid"],
        }

        url = options["url"]
        template = url
        url = Environment().from_string(template).render(values)

        if subscription["owner_user_uuid"] and url_is_localhost(url):
            # some services only listen on 127.0.0.1 and should not be accessible to users
            logger.warning(
                'Rejecting callback from user "%s" to url "%s": remote host is localhost!',
                subscription["owner_user_uuid"],
                url,
            )
            return

        content_type = options.get("content_type")

        body = options.get("body")
        if body:
            template = body
            body = Environment().from_string(template).render(values)
            body = body.encode("utf-8")
        else:
            body = json.dumps(event["data"])
            content_type = "application/json"

        if content_type:
            headers["Content-Type"] = content_type

        verify = options.get("verify_certificate")
        if verify:
            verify = True if verify == "true" else verify
            verify = False if verify == "false" else verify

        # TODO(sileht): In the best world we would report back
        # errors to the user, when we reach max retries maybe with a celery
        # result store, to keep it only temporary, then the API can retrieve
        # last error to returns them to the user.
        exponential_backoff = int(random.uniform(2, 4) ** self.request.retries)

        try:
            with requests.request(
                options["method"],
                url,
                data=body,
                verify=verify,
                headers=headers,
                # NOTE(sileht): This is only about TCP timeout issue, not the
                # while HTTP call
                timeout=REQUESTS_TIMEOUT,
                # NOTE(sileht): We don't care of the body, and we don't want to
                # download gigabytes of data for nothing or having the http
                # connection frozen because the server doesn't return the full
                # body. So stream the response, and the context manager with
                # close the request a soon as it return or raise a exception.
                # No body will be read ever.
                stream=True,
            ) as r:
                r.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            if exc.response.status_code == 410:
                logger.info(
                    "http request fail, service is gone ({}/{}): "
                    "'{} {} [{}]' {}".format(
                        self.request.retries,
                        self.max_retries,
                        options["method"],
                        url,
                        exc.response.status_code,
                        exc.response.text,
                    )
                )
            else:
                logger.info(
                    "http request fail, retrying ({}/{}): "
                    "'{} {} [{}]' {}".format(
                        self.request.retries,
                        self.max_retries,
                        options["method"],
                        url,
                        exc.response.status_code,
                        exc.response.text,
                    )
                )
                self.retry(exc=exc, countdown=exponential_backoff)

        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.TooManyRedirects,
        ) as exc:
            logger.info(
                "http request fail, retrying ({}/{}): {}".format(
                    self.request.retries, self.max_retries, options["method"], url, exc
                )
            )
            self.retry(exc=exc, countdown=exponential_backoff)

    return http_callback


def url_is_localhost(url):
    remote_host = urllib.parse.urlparse(url).hostname
    remote_address = socket.gethostbyname(remote_host)
    return remote_address == "127.0.0.1"
