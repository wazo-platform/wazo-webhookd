# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from functools import wraps

from .base import VALID_TOKEN


def subscription(subscription_args):
    '''This decorator is only compatible with instance methods, not pure functions.'''
    def decorator(decorated):
        @wraps(decorated)
        def wrapper(self, *args, **kwargs):
            webhookd = self.make_webhookd(VALID_TOKEN)
            new_subscription = webhookd.subscriptions.create(subscription_args)
            try:
                result = decorated(self, *args, **kwargs)
            finally:
                webhookd.subscriptions.delete(new_subscription['uuid'])
            return result
        return wrapper
    return decorator
