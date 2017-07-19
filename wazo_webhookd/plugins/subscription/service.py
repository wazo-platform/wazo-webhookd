# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
from wazo_webhookd.core.database.models import Subscription

from .exceptions import NoSuchSubscription


class SubscriptionService(object):

    def __init__(self, config):
        engine = create_engine(config['db_uri'])
        self._Session = scoped_session(sessionmaker())
        self._Session.configure(bind=engine)

    @contextmanager
    def new_session(self):
        session = self._Session()
        try:
            yield session
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            self._Session.remove()

    def list(self):
        with self.new_session() as session:
            result = session.query(Subscription).options(joinedload('events_'), joinedload('options')).all()
            session.expunge_all()
            return result

    def get(self, subscription_id):
        with self.new_session() as session:
            result = session.query(Subscription).options(joinedload('events_'), joinedload('options')).filter(Subscription.uuid == subscription_id).first()
            if result is None:
                raise NoSuchSubscription(subscription_id)

            session.expunge_all()
            return result

    def create(self, subscription):
        with self.new_session() as session:
            return session.add(Subscription(**subscription))

    def delete(self, subscription_id):
        with self.new_session() as session:
            if session.query(Subscription).filter(Subscription.uuid == subscription_id).first() is None:
                raise NoSuchSubscription(subscription_id)
            return session.query(Subscription).filter(Subscription.uuid == subscription_id).delete()
