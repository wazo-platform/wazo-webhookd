# Copyright 2017-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
import uuid
from functools import partial
from threading import Lock
from typing import TYPE_CHECKING, Any, Callable, Union

import kombu.exceptions

from wazo_webhookd.auth import master_tenant_uuid

from .celery_tasks import hook_runner_task
from .schema import subscription_schema

if TYPE_CHECKING:
    from importlib.metadata import EntryPoint

    from stevedore.extension import Extension
    from stevedore.named import NamedExtensionManager

    from ...bus import BusConsumer
    from ...database.models import Subscription
    from ...types import WebhookdConfigDict
    from .service import SubscriptionService


logger = logging.getLogger(__name__)


SubscriptionHeaders = dict[str, Any]
SubscriptionCallback = Callable[[dict[str, Any]], None]
SubscriptionCallbackRow = tuple[
    Union[SubscriptionCallback, None], list[str], SubscriptionHeaders
]

EMPTY_SUBSCRIPTION_CALLBACK: SubscriptionCallbackRow = None, [], {}


class SubscriptionBusEventHandler:
    def __init__(
        self,
        bus_consumer: BusConsumer,
        config: WebhookdConfigDict,
        service_manager: NamedExtensionManager,
        subscription_service: SubscriptionService,
    ) -> None:
        self._bus_consumer = bus_consumer
        self._subscription_callbacks: dict[str, SubscriptionCallbackRow] = {}
        self._lock = Lock()
        self._config = config
        self._service = subscription_service
        self._service.pubsub.subscribe('created', self.on_subscription_created)
        self._service.pubsub.subscribe('updated', self.on_subscription_updated)
        self._service.pubsub.subscribe('deleted', self.on_subscription_deleted)
        self._service_manager = service_manager

    def subscribe(self) -> None:
        for subscription in self._service.list():
            self._register(subscription)

    def on_subscription_created(self, subscription: Subscription) -> None:
        self._register(subscription)

    def on_subscription_updated(self, subscription: Subscription) -> None:
        self._update(subscription)

    def on_subscription_deleted(self, subscription: Subscription) -> None:
        self._unregister(subscription)

    @staticmethod
    def _build_headers(subscription: Subscription) -> SubscriptionHeaders:
        headers: SubscriptionHeaders = {
            'x-subscription': str(subscription.uuid),
        }
        user_uuid = subscription.events_user_uuid
        wazo_uuid = subscription.events_wazo_uuid
        tenant_uuid = subscription.owner_tenant_uuid

        if tenant_uuid != master_tenant_uuid:
            headers.update(tenant_uuid=str(tenant_uuid))
        if user_uuid:
            headers.update({f'user_uuid:{user_uuid}': True})
        if wazo_uuid:
            headers.update(origin_uuid=str(wazo_uuid))
        return headers

    def _register(self, subscription: Subscription):
        uuid = subscription.uuid
        data = subscription_schema.dump(subscription)

        with self._lock:
            fn, events, extra_headers = self._subscription_callbacks[uuid] = (
                partial(self._callback, data),
                subscription.events,
                self._build_headers(subscription),
            )

        for event in events:
            self._bus_consumer.subscribe(event, fn, headers=extra_headers)

    def _unregister(self, subscription):
        uuid = subscription.uuid
        with self._lock:
            fn, events, _ = self._subscription_callbacks.pop(
                uuid, EMPTY_SUBSCRIPTION_CALLBACK
            )

        for event in events:
            self._bus_consumer.unsubscribe(event, fn)

    def _update(self, subscription: Subscription):
        uuid = subscription.uuid
        data = subscription_schema.dump(subscription)
        headers = self._build_headers(subscription)
        fn = partial(self._callback, data)

        with self._lock:
            prev_fn, prev_events, prev_headers = self._subscription_callbacks.pop(uuid)

        all_events = set(subscription.events) | set(prev_events)

        for event in all_events:
            if event not in subscription.events:  # removed events
                self._bus_consumer.unsubscribe(event, prev_fn)
            elif event not in prev_events:  # newly added event
                self._bus_consumer.subscribe(event, fn, headers=headers)
            elif headers != prev_headers:  # headers changed
                self._bus_consumer.subscribe(event, fn, headers=headers)
                self._bus_consumer.unsubscribe(event, prev_fn)
            else:  # only update callback
                self._bus_consumer.unsubscribe(event, prev_fn)
                self._bus_consumer.subscribe(event, fn, headers=headers)

        with self._lock:
            self._subscription_callbacks[uuid] = (fn, subscription.events, headers)

    def _callback(self, subscription: Subscription, payload: dict[str, Any]) -> None:
        try:
            service: Extension = self._service_manager[subscription['service']]
        except KeyError:
            logger.error(
                '%s: no such service plugin. Subscription "%s" disabled',
                subscription['service'],
                subscription['name'],
            )
            return

        try:
            hook_uuid = str(uuid.uuid4())

            # Stevedore now uses importlib.metadata.Entrypoint, which does not have a
            # __str__ method for formatting, so we must build the name manually.
            entry_point: EntryPoint = service.entry_point
            entry_point_name = (
                f'{entry_point.name} = {entry_point.module}:{entry_point.attr}'
            )
            if extras := entry_point.extras:
                entry_point_name += f' [{",".join(extras)}]'

            task_args = (
                hook_uuid,
                entry_point_name,
                dict(self._config),
                subscription,
                payload,
            )
            hook_runner_task.delay(*task_args)
        except kombu.exceptions.OperationalError:
            # NOTE(sileht): That's not perfect in real life, because if celery
            # lose the connection, we have a good chance that our bus lose it
            # too. Anyway, we can requeue it, in case of our bus is faster to
            # reconnect, we are fine. Otherwise, we have an exception because of
            # disconnection and our bus will get this message again on
            # reconnection.
            raise
        except Exception:
            # NOTE(sileht): If we have a programming error, don't retry forever
            raise
