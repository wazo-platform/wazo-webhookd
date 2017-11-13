# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from functools import wraps
from wazo_webhookd_client.exceptions import WebhookdError

from .base import VALID_TOKEN


def subscription(subscription_args):
    '''This decorator is only compatible with instance methods, not pure functions.'''
    def decorator(decorated):
        @wraps(decorated)
        def wrapper(self, *args, **kwargs):
            webhookd = self.make_webhookd(VALID_TOKEN)
            new_subscription = webhookd.subscriptions.create(subscription_args)
            args = list(args) + [new_subscription]
            try:
                result = decorated(self, *args, **kwargs)
            finally:
                try:
                    webhookd = self.make_webhookd(VALID_TOKEN)
                    webhookd.subscriptions.delete(new_subscription['uuid'])
                except WebhookdError as e:
                    if e.status_code != 404:
                        raise
            return result
        return wrapper
    return decorator
