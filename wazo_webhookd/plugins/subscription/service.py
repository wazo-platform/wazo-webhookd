# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
from wazo_webhookd.database.models import Subscription
from xivo.pubsub import Pubsub

from .exceptions import NoSuchSubscription


class SubscriptionService(object):

    def __init__(self, config):
        engine = create_engine(config['db_uri'])
        self._Session = scoped_session(sessionmaker())
        self._Session.configure(bind=engine)
        self.pubsub = Pubsub()

    @contextmanager
    def rw_session(self):
        session = self._Session()
        try:
            yield session
            session.commit()
        except:
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

    def list(self, owner_user_uuid=None):
        with self.ro_session() as session:
            query = session.query(Subscription)
            if owner_user_uuid:
                query = query.filter(Subscription.owner_user_uuid == owner_user_uuid)
            return query.all()

    def get(self, subscription_uuid, owner_user_uuid=None):
        with self.ro_session() as session:
            query = session.query(Subscription).filter(Subscription.uuid == subscription_uuid)
            if owner_user_uuid:
                query = query.filter(Subscription.owner_user_uuid == owner_user_uuid)
            result = query.first()
            if result is None:
                raise NoSuchSubscription(subscription_uuid)

            return result

    def create(self, subscription):
        with self.rw_session() as session:
            new_subscription = Subscription(**subscription)
            session.add(new_subscription)
            self.pubsub.publish('created', new_subscription)
            return new_subscription

    def update(self, subscription_uuid, new_subscription):
        with self.rw_session() as session:
            subscription = session.query(Subscription).get(subscription_uuid)
            if subscription is None:
                raise NoSuchSubscription(subscription_uuid)

            subscription.clear_relations()
            session.flush()
            subscription.update(**new_subscription)
            session.flush()
            self.pubsub.publish('updated', subscription)

            session.expunge_all()
            return subscription

    def update_as_user(self, subscription_uuid, new_subscription, owner_user_uuid):
        with self.ro_session() as session:
            subscription = (session
                            .query(Subscription)
                            .filter(Subscription.uuid == subscription_uuid)
                            .filter(Subscription.owner_user_uuid == owner_user_uuid)
                            .first())
            if subscription is None:
                raise NoSuchSubscription(subscription_uuid)

        self.update(subscription_uuid, new_subscription)

    def delete(self, subscription_uuid):
        with self.rw_session() as session:
            subscription = session.query(Subscription).get(subscription_uuid)
            if subscription is None:
                raise NoSuchSubscription(subscription_uuid)
            session.query(Subscription).filter(Subscription.uuid == subscription_uuid).delete()
            self.pubsub.publish('deleted', subscription)

    def delete_as_user(self, subscription_uuid, user_uuid):
        with self.ro_session() as session:
            subscription = (session
                            .query(Subscription)
                            .filter(Subscription.uuid == subscription_uuid)
                            .filter(Subscription.owner_user_uuid == user_uuid)
                            .first())
            if subscription is None:
                raise NoSuchSubscription(subscription_uuid)

        self.delete(subscription_uuid)
