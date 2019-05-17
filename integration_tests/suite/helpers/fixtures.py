# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import copy
from functools import wraps
from wazo_webhookd_client.exceptions import WebhookdError

from .base import VALID_TOKEN


def subscription(subscription_args, track_test_name=True):
    '''This decorator is only compatible with instance methods, not pure functions.'''

    def decorator(decorated):
        @wraps(decorated)
        def wrapper(self, *args, **kwargs):
            webhookd = self.make_webhookd(VALID_TOKEN)

            sub = copy.deepcopy(subscription_args)
            if track_test_name:
                # Add test name to help debugging
                sep = "&" if "?" in sub['config']['url'] else "?"
                sub['config']['url'] += sep + "test_case=" + decorated.__name__

            new_subscription = webhookd.subscriptions.create(sub)
            self.ensure_webhookd_consume_uuid(new_subscription['uuid'])

            args = list(args) + [new_subscription]
            try:
                return decorated(self, *args, **kwargs)
            finally:
                try:
                    webhookd = self.make_webhookd(VALID_TOKEN)
                    webhookd.subscriptions.delete(new_subscription['uuid'])
                except WebhookdError as e:
                    if e.status_code != 404:
                        raise

                self.ensure_webhookd_not_consume_uuid(new_subscription['uuid'])

        return wrapper

    return decorator
