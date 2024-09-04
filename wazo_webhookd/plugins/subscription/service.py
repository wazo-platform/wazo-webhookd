# Copyright 2017-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from sqlalchemy import and_, create_engine, distinct, exc, func, or_
from sqlalchemy.orm import scoped_session, sessionmaker
from xivo.pubsub import Pubsub

from wazo_webhookd.database.models import (
    Subscription,
    SubscriptionLog,
    SubscriptionMetadatum,
)

from .exceptions import NoSuchSubscription

if TYPE_CHECKING:
    from ...types import WebhookdConfigDict


logger = logging.getLogger(__name__)


class SubscriptionService:
    # NOTE(sileht): We share the pubsub object, so a plugin that instantiate
    # other services (like push mobile) will continue work.

    pubsub = Pubsub()

    def __init__(self, config: WebhookdConfigDict) -> None:
        self._engine = create_engine(
            config['db_uri'],
            pool_size=config['rest_api']['max_threads'],
            pool_pre_ping=True,
        )
        self._Session: scoped_session = scoped_session(sessionmaker())
        self._Session.configure(bind=self._engine)

    def close(self) -> None:
        self._Session.close()
        self._engine.dispose()

    @contextmanager
    def rw_session(self) -> Generator[scoped_session, None, None]:
        session = self._Session()
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            self._Session.remove()

    @contextmanager
    def ro_session(self) -> Generator[scoped_session, None, None]:
        session = self._Session()
        try:
            yield session
        finally:
            self._Session.remove()

    def list(self, owner_tenant_uuids=None, owner_user_uuid=None, search_metadata=None):
        with self.ro_session() as session:
            query = session.query(Subscription)
            if owner_tenant_uuids:
                query = query.filter(
                    Subscription.owner_tenant_uuid.in_(owner_tenant_uuids)
                )
            if owner_user_uuid:
                query = query.filter(Subscription.owner_user_uuid == owner_user_uuid)
            if search_metadata:
                subquery = (
                    session.query(SubscriptionMetadatum.subscription_uuid)
                    .filter(
                        or_(
                            *[
                                and_(
                                    SubscriptionMetadatum.key == key,
                                    SubscriptionMetadatum.value == value,
                                )
                                for key, value in search_metadata.items()
                            ]
                        )
                    )
                    .group_by(SubscriptionMetadatum.subscription_uuid)
                    .having(
                        func.count(distinct(SubscriptionMetadatum.key))
                        == len(search_metadata)
                    )
                )
                query = query.filter(Subscription.uuid.in_(subquery))
            return query.all()

    def _get(
        self, session, subscription_uuid, owner_tenant_uuids=None, owner_user_uuid=None
    ):
        query = session.query(Subscription)
        query = query.filter(Subscription.uuid == subscription_uuid)
        if owner_tenant_uuids:
            query = query.filter(Subscription.owner_tenant_uuid.in_(owner_tenant_uuids))
        if owner_user_uuid:
            query = query.filter(Subscription.owner_user_uuid == owner_user_uuid)

        result = query.one_or_none()
        if result is None:
            raise NoSuchSubscription(subscription_uuid)

        return result

    def get(self, subscription_uuid, owner_tenant_uuids=None, owner_user_uuid=None):
        with self.ro_session() as session:
            return self._get(
                session, subscription_uuid, owner_tenant_uuids, owner_user_uuid
            )

    def create(self, new_subscription):
        with self.rw_session() as session:
            subscription = Subscription()
            subscription.from_schema(**new_subscription)
            subscription = session.merge(subscription)
            session.flush()
            session.expire_all()
            subscription.make_transient()
            self.pubsub.publish('created', subscription)
            return subscription

    def update(
        self,
        subscription_uuid,
        new_subscription,
        owner_tenant_uuids=None,
        owner_user_uuid=None,
    ):
        with self.rw_session() as session:
            subscription = self._get(
                session, subscription_uuid, owner_tenant_uuids, owner_user_uuid
            )
            subscription.clear_relations()
            session.flush()
            subscription.from_schema(**new_subscription)
            session.flush()
            session.expire_all()
            subscription.make_transient()
            self.pubsub.publish('updated', subscription)
            return subscription

    def delete(self, subscription_uuid, owner_tenant_uuids=None, owner_user_uuid=None):
        with self.rw_session() as session:
            subscription = self._get(
                session, subscription_uuid, owner_tenant_uuids, owner_user_uuid
            )
            session.delete(subscription)
            self.pubsub.publish('deleted', subscription)

    def get_logs(
        self,
        subscription_uuid,
        from_date=None,
        limit=None,
        offset=None,
        order='started_at',
        direction='desc',
        search=None,
    ):
        with self.ro_session() as session:
            query = session.query(SubscriptionLog).filter(
                SubscriptionLog.subscription_uuid == subscription_uuid
            )
            if from_date is not None:
                query = query.filter(SubscriptionLog.started_at >= from_date)

            order_column = getattr(SubscriptionLog, order)
            order_column = (
                order_column.asc() if direction == 'asc' else order_column.desc()
            )
            query = query.order_by(order_column)

            if limit is not None:
                query = query.limit(limit)
            if offset is not None:
                query = query.offset(offset)

            if search is not None:
                # TODO(sileht): search is not implemented yet
                logger.warning(
                    "search parameter have been used while " "not implemented"
                )
                pass

            return query.all()

    def create_hook_log(
        self,
        uuid,
        subscription_uuid,
        status,
        attempts,
        max_attempts,
        started_at,
        ended_at,
        event,
        detail,
    ):
        with self.rw_session() as session:
            hooklog = SubscriptionLog(
                uuid=uuid,
                subscription_uuid=subscription_uuid,
                status=status,
                attempts=attempts,
                max_attempts=max_attempts,
                started_at=started_at,
                ended_at=ended_at,
                event=event,
                detail=detail,
            )
            session.add(hooklog)
            try:
                session.commit()
            except exc.IntegrityError as e:
                if "violates foreign key constraint" in str(e):
                    logger.warning(
                        "subscription %s have been deleted in the meantime",
                        subscription_uuid,
                    )
                    session.rollback()
                else:
                    raise
