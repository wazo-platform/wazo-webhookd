# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import contextlib
import logging

import requests

logger = logging.getLogger(__name__)


class HookExpectedError(Exception):
    def __init__(self, detail):
        self.detail = detail
        super(HookExpectedError, self).__init__()


class HookRetry(Exception):
    def __init__(self, detail):
        self.detail = detail
        super(HookRetry, self).__init__()


@contextlib.contextmanager
def requests_automatic_hook_retry(task):
    try:
        yield
    except requests.exceptions.HTTPError as exc:
        if exc.response.status_code == 410:
            logger.info(
                "http request fail, service is gone (%d/%d): '%s %s [%s]' %s",
                task.request.retries,
                task.max_retries,
                exc.request.method,
                exc.request.url,
                exc.response.status_code,
                exc.response.text
            )
            raise HookExpectedError({
                "error": str(exc),
                "request_method": exc.request.method,
                "request_url": exc.request.url,
                "request_body": exc.request.body,
                "request_headers": dict(exc.request.headers),
                "response_status_code": exc.response.status_code,
                "response_headers": dict(exc.response.headers),
                "response_body": exc.response.text,
            })
        else:
            logger.info(
                "http request fail, retrying (%s/%s): '%s %s [%s]' %s",
                task.request.retries,
                task.max_retries,
                exc.request.method,
                exc.request.url,
                exc.response.status_code,
                exc.response.text
            )
            raise HookRetry({
                "error": str(exc),
                "request_method": exc.request.method,
                "request_url": exc.request.url,
                "request_body": exc.request.body,
                "request_headers": dict(exc.request.headers),
                "response_status_code": exc.response.status_code,
                "response_headers": dict(exc.response.headers),
                "response_body": exc.response.text,
            })

    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.TooManyRedirects
    ) as exc:
        logger.info(
            "http request fail, retrying (%s/%s): '%s %s [%s]'",
            task.request.retries,
            task.max_retries,
            exc.request.method,
            exc.request.url,
            exc
        )
        raise HookRetry({
            "error": str(exc),
            "request_method": exc.request.method,
            "request_url": exc.request.url,
            "request_body": exc.request.body,
            "request_headers": dict(exc.request.headers),
            "response_status_code": None,
            "response_headers": {},
            "response_body": "",
        })


def requests_automatic_detail(response):
    return {
        "request_method": response.request.method,
        "request_url": response.request.url,
        "request_body": response.request.body,
        "request_headers": dict(response.request.headers),
        "response_status_code": response.status_code,
        "response_headers": dict(response.headers),
        "response_body": response.text,
    }
