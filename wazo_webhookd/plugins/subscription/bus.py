# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import datetime
import functools
import logging
import kombu.exceptions
from pkg_resources import EntryPoint
import uuid

import celery

from wazo_webhookd.celery import app
from wazo_webhookd.services.helpers import HookRetry, HookExpectedError

from .schema import subscription_schema
from .service import SubscriptionService

logger = logging.getLogger(__name__)


@app.task(bind=True)
def hook_runner_task(task, hook_uuid, ep_name, config, subscription, event):
    service = SubscriptionService(config)
    try:
        hook_runner(service, task, hook_uuid, ep_name, config, subscription, event)
    finally:
        service.close()


def hook_runner(service, task, hook_uuid, ep_name, config, subscription, event):

    hook = EntryPoint.parse(ep_name).resolve()
    logger.info("running hook %s (%s) for event: %s", ep_name, hook_uuid, event)

    try:
        event_name = event['data']['name']
    except KeyError:
        event_name = '<unknown>'

    started = datetime.datetime.utcnow()
    try:
        detail = hook.run(task, config, subscription, event)
    except HookRetry as e:
        if task.request.retries + 1 == config["hook_max_attempts"]:
            verb = "reached max retries"
            status = "error"
        else:
            verb = "will retry"
            status = "failure"
        logger.error(
            "Hook `%s/%s` (%s) %s (%s/%s): %s",
            ep_name,
            hook_uuid,
            event_name,
            verb,
            task.request.retries + 1,
            config["hook_max_attempts"],
            e.detail,
        )
        ended = datetime.datetime.utcnow()
        service.create_hook_log(
            hook_uuid,
            subscription["uuid"],
            status,
            task.request.retries + 1,
            config["hook_max_attempts"],
            started,
            ended,
            event,
            e.detail,
        )

        retry_backoff = int(2 ** task.request.retries)
        try:
            task.retry(
                countdown=retry_backoff, max_retries=config["hook_max_attempts"] - 1
            )
        except celery.exceptions.MaxRetriesExceededError:
            return
    except Exception as e:
        if isinstance(e, HookExpectedError):
            detail = e.detail
            logger.error(
                "Hook `%s/%s` (%s) failure: %s", ep_name, hook_uuid, event_name, detail
            )
        else:
            # TODO(sileht): Maybe we should not record the raw error
            detail = {'error': str(e)}
            logger.error(
                "Hook `%s/%s` (%s) error: %s",
                ep_name,
                hook_uuid,
                event_name,
                detail,
                exc_info=True,
            )
        ended = datetime.datetime.utcnow()
        service.create_hook_log(
            hook_uuid,
            subscription["uuid"],
            "error",
            task.request.retries + 1,
            config["hook_max_attempts"],
            started,
            ended,
            event,
            detail,
        )

    else:
        logger.debug(
            "Hook `%s/%s` (%s) succeed: %s", ep_name, hook_uuid, event_name, detail
        )
        ended = datetime.datetime.utcnow()
        service.create_hook_log(
            hook_uuid,
            subscription["uuid"],
            "success",
            task.request.retries + 1,
            config["hook_max_attempts"],
            started,
            ended,
            event,
            detail or {},
        )


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
