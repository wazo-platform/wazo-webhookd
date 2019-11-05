# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import os
from contextlib import closing

import requests
from hamcrest import assert_that
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

from wazo_webhookd.database.models import Subscription

from .helpers.base import BaseIntegrationTest
from .helpers.base import MASTER_TOKEN
from .helpers.fixtures import subscription
from .helpers.wait_strategy import NoWaitStrategy

DB_URI = os.getenv('DB_URI', 'postgresql://asterisk:proformatique@localhost:{port}')


USER_1_UUID = '2eeb57e9-0506-4866-bce6-b626411fd133'
USER_2_UUID = 'cd030e68-ace9-4ad4-bc4e-13c8dec67898'

TEST_SUBSCRIPTION = {
    'name': 'test',
    'service': 'http',
    'config': {'url': 'http://test.example.com', 'method': 'get'},
    'events': ['test'],
}

TEST_SUBSCRIPTION_USER_1 = {
    'name': 'test_user1',
    'service': 'http',
    'config': {'url': 'http://test.example.com', 'method': 'get'},
    'events': ['test'],
    'owner_user_uuid': USER_1_UUID,
}

TEST_SUBSCRIPTION_USER_2 = {
    'name': 'test_user2',
    'service': 'http',
    'config': {'url': 'http://test.example.com', 'method': 'get'},
    'events': ['test'],
    'owner_user_uuid': USER_2_UUID,
}


class TestTenantMigration(BaseIntegrationTest):

    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def setUp(self):
        super().setUp()
        self.Session = scoped_session(sessionmaker())
        engine = create_engine(DB_URI.format(port=self.service_port(5432, 'postgres')))
        self.Session.configure(bind=engine)
        self.configured_wazo_auth()

    @subscription(TEST_SUBSCRIPTION)
    @subscription(TEST_SUBSCRIPTION_USER_1)
    @subscription(TEST_SUBSCRIPTION_USER_2)
    def test_tenant_migration(self, _, __, ___):
        # Set no tenant to all subscriptions
        with closing(self.Session()) as session:
            query = session.query(Subscription)
            query.update(
                {Subscription.owner_tenant_uuid: "00000000-0000-0000-0000-000000000000"}
            )

        url = 'https://localhost:{port}/1.0/tenant-migration'.format(
            port=self.service_port(9300, 'webhookd')
        )

        payload = [
            {'owner_user_uuid': USER_1_UUID, 'owner_tenant_uuid': USER_1_UUID},
            {'owner_user_uuid': USER_2_UUID, 'owner_tenant_uuid': USER_2_UUID},
        ]
        headers = {'X-Auth-Token': MASTER_TOKEN, 'Content-Type': 'application/json'}
        resp = requests.post(url, json=payload, headers=headers, verify=False)
        resp.raise_for_status()

        with closing(self.Session()) as session:
            query = session.query(Subscription)
            for sub in query.all():
                if sub.owner_user_uuid:
                    assert_that(sub.owner_user_uuid, sub.owner_tenant_uuid)
                else:
                    assert_that(sub.owner_tenant_uuid, USER_1_UUID)
