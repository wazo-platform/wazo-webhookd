# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import datetime
import logging
from pkg_resources import EntryPoint

from wazo_webhookd.exceptions import HookRetry
from wazo_webhookd.celery import app

from .schema import subscription_schema
from .service import SubscriptionService

logger = logging.getLogger(__name__)

# NOTE(sileht): overall retry will be 30 minutes
MAX_RETRIES = 10


@app.task(bind=True, max_retries=MAX_RETRIES)
def hook_runner(task, ep_name, config, subscription, event):

    hook = EntryPoint.parse(ep_name).resolve()

    service = SubscriptionService(config)
    started = datetime.datetime.utcnow()
    try:
        detail = hook.run(task, config, subscription, event)
    except HookRetry as e:
        logger.error("Hook `%s` ask retries (%s/%s)", ep_name,
                     task.request.retries, MAX_RETRIES)
        if task.request.retries == MAX_RETRIES:
            status = "fatal"
        else:
            status = "failure"
        ended = datetime.datetime.utcnow()
        service.create_hook_log(subscription["uuid"], status,
                                task.request.retries, started, ended, e.detail)

        retry_backoff = int(2 ** task.request.retries)
        task.retry(countdown=retry_backoff)
    except Exception as e:
        logger.error("Hook `%s` failure", ep_name, exc_info=True)
        ended = datetime.datetime.utcnow()
        service.create_hook_log(subscription["uuid"], "fatal",
                                task.request.retries, started, ended,
                                # TODO(sileht): Maybe we should not record the
                                # raw error
                                {'error': str(e)})

    else:
        ended = datetime.datetime.utcnow()
        service.create_hook_log(subscription["uuid"], "success",
                                task.request.retries, started, ended,
                                detail or {})


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
        self._bus_consumer.change_subscription(subscription.uuid,
                                               subscription.events,
                                               subscription.events_user_uuid,
                                               subscription.events_wazo_uuid,
                                               self._make_callback(subscription))

    def on_subscription_deleted(self, subscription):
        self._bus_consumer.unsubscribe_from_event_names(subscription.uuid)

    def _add_one_subscription_to_bus(self, subscription):
        self._bus_consumer.subscribe_to_event_names(subscription.uuid,
                                                    subscription.events,
                                                    subscription.events_user_uuid,
                                                    subscription.events_wazo_uuid,
                                                    self._make_callback(subscription))

    def _make_callback(self, subscription):
        try:
            service = self._service_manager[subscription.service]
        except KeyError:
            logger.error('%s: no such service plugin. Subscription "%s" disabled',
                         subscription.service,
                         subscription.name)
            return

        subscription = subscription_schema.dump(subscription).data

        def callback(event, _):
            hook_runner.apply_async([str(service.entry_point), self._config.data, subscription, event])

        return callback
