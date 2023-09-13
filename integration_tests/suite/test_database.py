# Copyright 2017-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import datetime
import os
import uuid

from contextlib import contextmanager
from functools import partial
from hamcrest import (
    assert_that,
    calling,
    equal_to,
    has_entries,
    is_,
    none,
    not_none,
    raises,
)
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker, scoped_session
from wazo_test_helpers.asset_launching_test_case import AssetLaunchingTestCase
from wazo_webhookd.database.models import Subscription
from wazo_webhookd.database.models import SubscriptionEvent
from wazo_webhookd.database.models import SubscriptionOption
from wazo_webhookd.database.purger import SubscriptionLogsPurger
from wazo_webhookd.plugins.subscription.service import SubscriptionService

DB_URI = os.getenv('DB_URI', 'postgresql://wazo-webhookd:Secr7t@127.0.0.1:{port}')


class TestDatabase(AssetLaunchingTestCase):
    asset = 'database'
    assets_root = os.path.join(os.path.dirname(__file__), '..', 'assets')
    service = 'postgres'

    def setUp(self):
        super().setUp()
        self.db_uri = DB_URI.format(port=self.service_port(5432, 'postgres'))
        self._Session = scoped_session(sessionmaker())
        engine = create_engine(self.db_uri)
        self._Session.configure(bind=engine)

    def _some_config(self, **args):
        return {
            'db_uri': self.db_uri,
            'rest_api': {
                'max_threads': 10,
            },
        }

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
            subscription = Subscription(
                uuid=str(uuid.uuid4()), name='test', owner_tenant_uuid=str(uuid.uuid4())
            )
            subscription_event = SubscriptionEvent(
                event_name='test', subscription_uuid=subscription.uuid
            )
            subscription_option = SubscriptionOption(
                name='test', subscription_uuid=subscription.uuid
            )
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
        subscription = Subscription(
            uuid=str(uuid.uuid4()), name='test', owner_tenant_uuid=str(uuid.uuid4())
        )
        subscription_event = SubscriptionEvent(
            event_name='test', subscription_uuid=subscription.uuid
        )
        subscription_event_2 = SubscriptionEvent(
            event_name='test', subscription_uuid=subscription.uuid
        )

        session = self._Session()
        session.add(subscription)
        session.add(subscription_event)
        session.add(subscription_event_2)

        assert_that(calling(session.commit).with_args(), raises(IntegrityError))

        self._Session.remove()

    def test_subscription_option_unique(self):
        subscription = Subscription(
            uuid=str(uuid.uuid4()), name='test', owner_tenant_uuid=str(uuid.uuid4())
        )
        subscription_option = SubscriptionOption(
            name='test', subscription_uuid=subscription.uuid
        )
        subscription_option_2 = SubscriptionOption(
            name='test', subscription_uuid=subscription.uuid
        )

        session = self._Session()
        session.add(subscription)
        session.add(subscription_option)
        session.add(subscription_option_2)

        assert_that(calling(session.commit).with_args(), raises(IntegrityError))

        self._Session.remove()

    def test_subscription_pubsub_create(self):
        service = SubscriptionService(self._some_config())

        tracker = {'uuid': None}

        def on_subscription(subscription):
            tracker['uuid'] = subscription.uuid

        service.pubsub.subscribe('created', on_subscription)
        service.create(
            {
                'name': 'test',
                'owner_tenant_uuid': str(uuid.uuid4()),
                'service': 'http',
                'config': {},
                'events': [],
            }
        )
        assert_that(tracker, has_entries({'uuid': is_(not_none())}))

    def test_subscription_pubsub_two_services(self):
        service1 = SubscriptionService(self._some_config())
        service2 = SubscriptionService(self._some_config())

        tracker = {}

        def on_subscription(service, _):
            tracker[service] = True

        service1.pubsub.subscribe('created', partial(on_subscription, "service1"))
        service2.pubsub.subscribe('created', partial(on_subscription, "service2"))

        service1.create(
            {
                'name': 'test',
                'owner_tenant_uuid': str(uuid.uuid4()),
                'service': 'http',
                'config': {},
                'events': [],
            }
        )
        assert_that(tracker, has_entries({'service1': True, 'service2': True}))

    def test_purger(self):
        service = SubscriptionService(self._some_config())
        subscription_uuid = service.create(
            {
                'name': 'test',
                'owner_tenant_uuid': str(uuid.uuid4()),
                'service': 'http',
                'config': {},
                'events': [],
            }
        ).uuid

        def add_log(days_ago):
            started_at = datetime.datetime.now() - datetime.timedelta(days=days_ago)
            service.create_hook_log(
                str(uuid.uuid4()),
                subscription_uuid,
                "failure",
                1,
                3,
                started_at,
                started_at + datetime.timedelta(minutes=1),
                {},
                {},
            )

        for days in range(5):
            add_log(days_ago=days)
            add_log(days_ago=days)

        logs = service.get_logs(subscription_uuid)
        assert_that(len(logs), equal_to(10))

        with service.rw_session() as session:
            days_to_purge = 2
            SubscriptionLogsPurger().purge(days_to_purge, session)

        logs = service.get_logs(subscription_uuid)
        assert_that(len(logs), equal_to(4))

    def test_subscription_log_on_subscription_deleted(self):
        service = SubscriptionService(self._some_config())
        subscription_uuid_not_found = str(uuid.uuid4())

        service.create_hook_log(
            uuid=str(uuid.uuid4()),
            subscription_uuid=subscription_uuid_not_found,
            status="failure",
            attempts=1,
            max_attempts=3,
            started_at=datetime.datetime.now(),
            ended_at=datetime.datetime.now() + datetime.timedelta(minutes=1),
            event={},
            detail={},
        )

        # assert no exception
