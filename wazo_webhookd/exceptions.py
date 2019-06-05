# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later


import contextlib
import logging

import requests

from xivo.rest_api_helpers import APIException

logger = logging.getLogger(__name__)


class TokenWithUserUUIDRequiredError(APIException):

    def __init__(self):
        super(TokenWithUserUUIDRequiredError, self).__init__(
            status_code=400,
            message='A valid token with a user UUID is required',
            error_id='token-with-user-uuid-required',
        )


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
            logger.info("http request fail, service is gone ({}/{}): "
                        "'{} [{}]' {}".format(
                            task.request.retries,
                            task.max_retries,
                            exc.request.method,
                            exc.request.url,
                            exc.response.status_code,
                            exc.response.text
                        ))
        else:
            logger.info("http request fail, retrying ({}/{}): "
                        "'{} {} [{}]' {}".format(
                            task.request.retries,
                            task.max_retries,
                            exc.request.method,
                            exc.request.url,
                            exc.response.status_code,
                            exc.response.text
                        ))
            raise HookRetry({
                "error": str(exc),
                "method": exc.request.method,
                "url": exc.request.url,
                "status_code": exc.response.status_code,
                "headers": dict(exc.response.headers),
                "body": exc.response.text,
            })

    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.TooManyRedirects
    ) as exc:
        logger.info("http request fail, retrying ({}/{}): {}".format(
            task.request.retries,
            task.max_retries,
            exc.request.method,
            exc.request.url,
            exc
        ))
        raise HookRetry({
            "error": str(exc),
            "method": exc.request.method,
            "url": exc.request.url,
            "status_code": None,
            "headers": {},
            "body": "",
        })
