# Copyright 2017-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import uuid

from contextlib import contextmanager
from hamcrest import assert_that
from hamcrest import calling
from hamcrest import is_
from hamcrest import none
from hamcrest import raises
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker, scoped_session
from xivo_test_helpers.asset_launching_test_case import AssetLaunchingTestCase
from wazo_webhookd.database.models import Subscription
from wazo_webhookd.database.models import SubscriptionEvent
from wazo_webhookd.database.models import SubscriptionOption

DB_URI = os.getenv('DB_URI', 'postgresql://asterisk:proformatique@localhost:{port}')


class TestDatabase(AssetLaunchingTestCase):

    asset = 'database'
    assets_root = os.path.join(os.path.dirname(__file__), '..', 'assets')
    service = 'postgresql'

    def setUp(self):
        super(TestDatabase, self).setUp()
        self._Session = scoped_session(sessionmaker())
        engine = create_engine(DB_URI.format(port=self.service_port(5432, 'postgres')))
        self._Session.configure(bind=engine)

    @contextmanager
    def new_session(self):
        session = self._Session()
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            self._Session.remove()

    def test_subscription_cascade(self):
        with self.new_session() as session:
            subscription = Subscription(uuid=str(uuid.uuid4()), name='test')
            subscription_event = SubscriptionEvent(event_name='test', subscription_uuid=subscription.uuid)
            subscription_option = SubscriptionOption(name='test', subscription_uuid=subscription.uuid)
            session.add(subscription)
            session.add(subscription_event)
            session.add(subscription_option)

        with self.new_session() as session:
            session.delete(subscription)

        with self.new_session() as session:
            event = session.query(SubscriptionEvent).first()
            option = session.query(SubscriptionOption).first()
            assert_that(event, is_(none()))
            assert_that(option, is_(none()))

    def test_subscription_event_unique(self):
        subscription = Subscription(uuid=str(uuid.uuid4()), name='test')
        subscription_event = SubscriptionEvent(event_name='test', subscription_uuid=subscription.uuid)
        subscription_event_2 = SubscriptionEvent(event_name='test', subscription_uuid=subscription.uuid)

        session = self._Session()
        session.add(subscription)
        session.add(subscription_event)
        session.add(subscription_event_2)

        assert_that(calling(session.commit).with_args(),
                    raises(IntegrityError))

        self._Session.remove()

    def test_subscription_option_unique(self):
        subscription = Subscription(uuid=str(uuid.uuid4()), name='test')
        subscription_option = SubscriptionOption(name='test', subscription_uuid=subscription.uuid)
        subscription_option_2 = SubscriptionOption(name='test', subscription_uuid=subscription.uuid)

        session = self._Session()
        session.add(subscription)
        session.add(subscription_option)
        session.add(subscription_option_2)

        assert_that(calling(session.commit).with_args(),
                    raises(IntegrityError))

        self._Session.remove()
