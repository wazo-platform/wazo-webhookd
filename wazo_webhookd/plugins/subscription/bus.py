# Copyright 2017-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import kombu.exceptions
import uuid

from collections import defaultdict
from functools import partial
from wazo_webhookd.auth import master_tenant_uuid
from .celery_tasks import hook_runner_task
from .schema import subscription_schema

logger = logging.getLogger(__name__)


class SubscriptionBusEventHandler:
    def __init__(self, bus_consumer, config, service_manager, subscription_service):
        self._bus_consumer = bus_consumer
        self._subscription_callbacks = defaultdict(list)
        self._config = config
        self._service = subscription_service
        self._service.pubsub.subscribe('created', self.on_subscription_created)
        self._service.pubsub.subscribe('updated', self.on_subscription_updated)
        self._service.pubsub.subscribe('deleted', self.on_subscription_deleted)
        self._service_manager = service_manager

    def subscribe(self):
        for subscription in self._service.list():
            self._register(subscription)

    def on_subscription_created(self, subscription):
        self._register(subscription)

    def on_subscription_updated(self, subscription):
        self._unregister(subscription)
        self._register(subscription)

    def on_subscription_deleted(self, subscription):
        self._unregister(subscription)

    @staticmethod
    def _build_headers(subscription):
        headers = {
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

    def _register(self, subscription):
        uuid = subscription.uuid
        data = subscription_schema.dump(subscription)
        extra_headers = self._build_headers(subscription)

        fn, events = self._subscription_callbacks[uuid] = (
            partial(self._callback, data),
            subscription.events,
        )

        for event in events:
            self._bus_consumer.subscribe(event, fn, headers=extra_headers)

    def _unregister(self, subscription):
        uuid = subscription.uuid
        fn, events = self._subscription_callbacks.pop(uuid, (None, []))

        for event in events:
            self._bus_consumer.unsubscribe(event, fn)

    def _callback(self, subscription, payload):
        try:
            service = self._service_manager[subscription['service']]
        except KeyError:
            logger.error(
                '%s: no such service plugin. Subscription "%s" disabled',
                subscription['service'],
                subscription['name'],
            )
            return

        try:
            hook_uuid = str(uuid.uuid4())
            hook_runner_task.s(
                hook_uuid,
                str(service.entry_point),
                self._config.data,
                subscription,
                payload,
            ).apply_async()
        except kombu.exceptions.OperationalError:
            # NOTE(sileht): That's not perfect in real life, because if celery
            # lose the connection, we have a good chance that our bus lose it
            # too. Anyways we can requeue it, in case of our bus is faster to
            # reconnect, we are fine. Otherise we have an exception because of
            # disconnection and our bus will get this message again on
            # reconnection.
            raise
        except Exception:
            # NOTE(sileht): We have a programming issue, we don't retry forever
            raise
