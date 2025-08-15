# Copyright 2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from wazo_bus import BusPublisher
from wazo_bus.resources.webhookd.events import (
    WebhookdSubscriptionCreatedEvent,
    WebhookdSubscriptionCreatedUserEvent,
    WebhookdSubscriptionDeletedEvent,
    WebhookdSubscriptionDeletedUserEvent,
    WebhookdSubscriptionUpdatedEvent,
    WebhookdSubscriptionUpdatedUserEvent,
)

from wazo_webhookd.database.models import Subscription

from .schema import subscription_schema, user_subscription_schema


class SubscriptionNotifier:
    def __init__(self, bus_publisher: BusPublisher):
        self._bus_publisher = bus_publisher

    def created(self, subscription: Subscription):
        """Publish webhookd_subscription_created event to the bus."""

        if subscription.owner_user_uuid:
            subscription_data = user_subscription_schema.dump(subscription)
            event = WebhookdSubscriptionCreatedUserEvent(
                subscription=subscription_data,
                tenant_uuid=subscription.owner_tenant_uuid,
                user_uuid=subscription.owner_user_uuid,
            )
        else:
            subscription_data = subscription_schema.dump(subscription)
            event = WebhookdSubscriptionCreatedEvent(
                subscription=subscription_data,
                tenant_uuid=subscription.owner_tenant_uuid,
            )
        self._bus_publisher.publish(event)

    def updated(self, subscription: Subscription):
        """Publish webhookd_subscription_updated event to the bus."""

        if subscription.owner_user_uuid:
            subscription_data = user_subscription_schema.dump(subscription)
            event = WebhookdSubscriptionUpdatedUserEvent(
                subscription=subscription_data,
                tenant_uuid=subscription.owner_tenant_uuid,
                user_uuid=subscription.owner_user_uuid,
            )
        else:
            subscription_data = subscription_schema.dump(subscription)
            event = WebhookdSubscriptionUpdatedEvent(
                subscription=subscription_data,
                tenant_uuid=subscription.owner_tenant_uuid,
            )
        self._bus_publisher.publish(event)

    def deleted(self, subscription: Subscription):
        """Publish webhookd_subscription_deleted event to the bus."""

        if subscription.owner_user_uuid:
            subscription_data = user_subscription_schema.dump(subscription)
            event = WebhookdSubscriptionDeletedUserEvent(
                subscription=subscription_data,
                tenant_uuid=subscription.owner_tenant_uuid,
                user_uuid=subscription.owner_user_uuid,
            )
        else:
            subscription_data = subscription_schema.dump(subscription)
            event = WebhookdSubscriptionDeletedEvent(
                subscription=subscription_data,
                tenant_uuid=subscription.owner_tenant_uuid,
            )
        self._bus_publisher.publish(event)
