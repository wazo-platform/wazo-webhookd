# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
import datetime
import logging
from pkg_resources import EntryPoint

import celery

from wazo_webhookd.celery import app
from wazo_webhookd.services.helpers import HookRetry, HookExpectedError

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
