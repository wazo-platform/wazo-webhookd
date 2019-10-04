# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import functools
import logging
import kombu.exceptions
import uuid

from .celery_tasks import hook_runner_task
from .schema import subscription_schema

logger = logging.getLogger(__name__)


class SubscriptionBusEventHandler:
    def __init__(self, bus_consumer, config, service_manager, subscription_service):
        self._bus_consumer = bus_consumer
        self._config = config
        self._service = subscription_service
        self._service.pubsub.subscribe('created', self.on_subscription_created)
        self._service.pubsub.subscribe('updated', self.on_subscription_updated)
        self._service.pubsub.subscribe('deleted', self.on_subscription_deleted)
        self._service_manager = service_manager

    def subscribe(self, bus_consumer):
        for subscription in self._service.list():
            self._add_one_subscription_to_bus(subscription)

    def on_subscription_created(self, subscription):
        self._add_one_subscription_to_bus(subscription)

    def on_subscription_updated(self, subscription):
        raw_subscription = subscription_schema.dump(subscription)
        self._bus_consumer.change_subscription(
            subscription.uuid,
            subscription.events,
            subscription.events_user_uuid,
            subscription.events_wazo_uuid,
            functools.partial(self._callback, raw_subscription),
        )

    def on_subscription_deleted(self, subscription):
        self._bus_consumer.unsubscribe_from_event_names(subscription.uuid)

    def _add_one_subscription_to_bus(self, subscription):
        raw_subscription = subscription_schema.dump(subscription)
        self._bus_consumer.subscribe_to_event_names(
            subscription.uuid,
            subscription.events,
            subscription.events_user_uuid,
            subscription.events_wazo_uuid,
            functools.partial(self._callback, raw_subscription),
        )

    def _callback(self, subscription, event, message):
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
                event,
            ).apply_async()
        except kombu.exceptions.OperationalError:
            # NOTE(sileht): That's not perfect in real life, because if celery
            # lose the connection, we have a good chance that our bus lose it
            # too. Anyways we can requeue it, in case of our bus is faster to
            # reconnect, we are fine. Otherise we have an exception because of
            # disconnection and our bus will get this message again on
            # reconnection.
            try:
                message.requeue()
            except Exception:
                logger.error("fail to requeue message")
            raise
        except Exception:
            # NOTE(sileht): We have a programming issue, we don't retry forever
            message.ack()
            raise
        else:
            message.ack()
