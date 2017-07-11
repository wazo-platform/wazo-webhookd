# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from wazo_webhookd.core.database.models import Subscription


class SubscriptionsService(object):

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
            return session.query(Subscription).join(Subscription.events).join(Subscription.options)
