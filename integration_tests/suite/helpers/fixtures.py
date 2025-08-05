# Copyright 2017-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import copy
from contextlib import contextmanager
from functools import wraps
from typing import Callable

from wazo_webhookd_client import Client as WebhookdClient
from wazo_webhookd_client.exceptions import WebhookdError

from .base import MASTER_TOKEN


class SubscriptionFixtureMixin:
    make_webhookd: Callable[..., WebhookdClient]
    ensure_webhookd_not_consume_subscription: Callable[..., None]
    ensure_webhookd_consume_subscription: Callable[..., None]

    @contextmanager
    def subscription(
        self,
        subscription_args,
        token=MASTER_TOKEN,
        tenant=None,
        auto_delete=True,
    ):
        webhookd = self.make_webhookd(token, tenant)

        sub = copy.deepcopy(subscription_args)

        new_subscription = webhookd.subscriptions.create(sub)
        self.ensure_webhookd_consume_subscription(new_subscription)

        try:
            yield new_subscription
        finally:
            if auto_delete:
                try:
                    webhookd = self.make_webhookd(
                        token, new_subscription['owner_tenant_uuid']
                    )
                    webhookd.subscriptions.delete(new_subscription['uuid'])
                except WebhookdError as e:
                    if e.status_code != 404:
                        raise

                self.ensure_webhookd_not_consume_subscription(new_subscription)

    @contextmanager
    def user_subscription(
        self,
        subscription_args,
        token=MASTER_TOKEN,
        tenant=None,
        auto_delete=True,
    ):
        webhookd = self.make_webhookd(token, tenant)

        sub = copy.deepcopy(subscription_args)

        new_subscription = webhookd.subscriptions.create_as_user(sub)
        self.ensure_webhookd_consume_subscription(new_subscription)

        try:
            yield new_subscription
        finally:
            if auto_delete:
                try:
                    webhookd = self.make_webhookd(
                        token, new_subscription['owner_tenant_uuid']
                    )
                    webhookd.subscriptions.delete_as_user(new_subscription['uuid'])
                except WebhookdError as e:
                    if e.status_code != 404:
                        raise

                self.ensure_webhookd_not_consume_subscription(new_subscription)


def subscription(
    subscription_args,
    track_test_name=True,
    token=MASTER_TOKEN,
    tenant=None,
    auto_delete=True,
):
    """This decorator is only compatible with instance methods, not pure functions."""

    def decorator(decorated):
        @wraps(decorated)
        def wrapper(self, *args, **kwargs):
            sub = copy.deepcopy(subscription_args)

            if track_test_name and sub['service'] == 'http':
                # Add test name to help debugging
                sep = "&" if "?" in sub['config']['url'] else "?"
                sub['config']['url'] += sep + "test_case=" + decorated.__name__

            with SubscriptionFixtureMixin.subscription(
                self, sub, token=token, tenant=tenant, auto_delete=auto_delete
            ) as subscription_:
                return decorated(self, *args, subscription_, **kwargs)

        return wrapper

    return decorator


def user_subscription(
    subscription_args,
    token=MASTER_TOKEN,
    tenant=None,
    auto_delete=True,
):
    def decorator(decorated):
        @wraps(decorated)
        def wrapper(self, *args, **kwargs):
            with SubscriptionFixtureMixin.user_subscription(
                self,
                subscription_args,
                token=token,
                tenant=tenant,
                auto_delete=auto_delete,
            ) as subscription_:
                return decorated(self, *args, subscription_, **kwargs)

        return wrapper

    return decorator
