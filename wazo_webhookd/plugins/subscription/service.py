# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from contextlib import contextmanager
from sqlalchemy import (
    and_,
    create_engine,
    distinct,
    func,
    or_,
)
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
from wazo_webhookd.database.models import (
    Subscription,
    SubscriptionMetadatum,
)
from xivo.pubsub import Pubsub

from .exceptions import NoSuchSubscription


class SubscriptionService(object):

    # NOTE(sileht): We share the pubsub object, so plugin that instanciate
    # another service (like push mobile) will continue work.

    pubsub = Pubsub()

    def __init__(self, config):
        engine = create_engine(config['db_uri'])
        self._Session = scoped_session(sessionmaker())
        self._Session.configure(bind=engine)

    @contextmanager
    def rw_session(self):
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
    def ro_session(self):
        session = self._Session()
        try:
            yield session
        finally:
            self._Session.remove()

    def list(self, owner_tenant_uuids=None, owner_user_uuid=None, search_metadata=None):
        with self.ro_session() as session:
            query = session.query(Subscription)
            if owner_tenant_uuids:
                query = query.filter(Subscription.owner_tenant_uuid.in_(owner_tenant_uuids))
            if owner_user_uuid:
                query = query.filter(Subscription.owner_user_uuid == owner_user_uuid)
            if search_metadata:
                subquery = (session.query(SubscriptionMetadatum.subscription_uuid)
                            .filter(or_(*[and_(SubscriptionMetadatum.key == key,
                                               SubscriptionMetadatum.value == value)
                                          for key, value in search_metadata.items()]))
                            .group_by(SubscriptionMetadatum.subscription_uuid)
                            .having(func.count(distinct(SubscriptionMetadatum.key)) == len(search_metadata)))
                query = query.filter(Subscription.uuid.in_(subquery))
            return query.all()

    def _get(self, session, subscription_uuid, owner_tenant_uuids, owner_user_uuid=None):
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
            return self._get(session, subscription_uuid, owner_tenant_uuids, owner_user_uuid)

    def create(self, subscription):
        with self.rw_session() as session:
            new_subscription = Subscription(**subscription)
            session.add(new_subscription)
            self.pubsub.publish('created', new_subscription)
            return new_subscription

    def update(self, subscription_uuid, new_subscription,
               owner_tenant_uuids=None, owner_user_uuid=None):
        with self.rw_session() as session:
            subscription = self._get(session, subscription_uuid, owner_tenant_uuids,
                                     owner_user_uuid)
            subscription.clear_relations()
            session.flush()
            subscription.update(**new_subscription)
            session.flush()
            self.pubsub.publish('updated', subscription)

            session.expunge_all()
            return subscription

    def delete(self, subscription_uuid, owner_tenant_uuids=None, owner_user_uuid=None):
        with self.rw_session() as session:
            subscription = self._get(session, subscription_uuid, owner_tenant_uuids,
                                     owner_user_uuid)
            session.delete(subscription)
            self.pubsub.publish('deleted', subscription)
