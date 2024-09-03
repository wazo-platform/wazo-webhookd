# Copyright 2019-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING, Any

import celery
from pkg_resources import EntryPoint

from wazo_webhookd.celery import app
from wazo_webhookd.services.helpers import HookExpectedError, HookRetry

from .service import SubscriptionService

if TYPE_CHECKING:
    from ...database.models import Subscription
    from ...types import WebhookdConfigDict


logger = logging.getLogger(__name__)

MAX_BODY_LOG_LENGTH = 250


def truncated(detail: Any) -> str:
    detail = str(detail)
    if len(detail) >= MAX_BODY_LOG_LENGTH:
        return detail[:MAX_BODY_LOG_LENGTH] + "... [truncated]"
    return detail


class ServiceTask(celery.Task):
    _service: SubscriptionService | None = None

    @classmethod
    def get_service(cls, config: WebhookdConfigDict) -> SubscriptionService:
        if cls._service is None:
            cls._service = SubscriptionService(config)
        return cls._service


@app.task(base=ServiceTask, bind=True)
def hook_runner_task(
    task: ServiceTask,
    hook_uuid: str,
    ep_name: str,
    config: WebhookdConfigDict,
    subscription: Subscription,
    event: dict[str, Any],
) -> None:
    service = task.get_service(config)

    hook = EntryPoint.parse(ep_name).resolve()
    logger.info("running hook %s (%s) for event: %s", ep_name, hook_uuid, event)

    try:
        event_name = event['name']
    except KeyError:
        event_name = '<unknown>'

    started = datetime.datetime.utcnow()
    try:
        detail = hook.run(task, config, subscription, event)
    except HookRetry as e:
        if task.request.retries + 1 >= config["hook_max_attempts"]:
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
            truncated(e.detail),
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

        if task.request.retries + 1 >= config["hook_max_attempts"]:
            return

        retry_backoff = int(2**task.request.retries)
        task.retry(countdown=retry_backoff)
    except Exception as e:
        if isinstance(e, HookExpectedError):
            detail = e.detail
            logger.error(
                "Hook `%s/%s` (%s) failure: %s",
                ep_name,
                hook_uuid,
                event_name,
                truncated(detail),
            )
        else:
            # TODO(sileht): Maybe we should not record the raw error
            detail = {'error': str(e)}
            logger.error(
                "Hook `%s/%s` (%s) error: %s",
                ep_name,
                hook_uuid,
                event_name,
                truncated(detail),
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
            "Hook `%s/%s` (%s) succeed: %s",
            ep_name,
            hook_uuid,
            event_name,
            truncated(detail),
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
