# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import contextlib
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
from wazo_webhookd.database.models import Subscription


logger = logging.getLogger(__name__)

TO_MIGRATE_TENANT_UUID = '00000000-0000-0000-0000-000000000000'


class WebhookTenantUpgradeService(object):
    def __init__(self, config):
        engine = create_engine(config['db_uri'])
        self._Session = scoped_session(sessionmaker())
        self._Session.configure(bind=engine)

    @contextlib.contextmanager
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

    def update_owner_tenant_uuid(self, owner_user_uuid, owner_tenant_uuid):
        logger.info(
            'updating user(%s) tenant to %s', owner_user_uuid, owner_tenant_uuid
        )
        with self.rw_session() as session:
            query = session.query(Subscription)
            query = query.filter(
                Subscription.owner_tenant_uuid == TO_MIGRATE_TENANT_UUID
            )
            query = query.filter(Subscription.owner_user_uuid == owner_user_uuid)
            query.update({Subscription.owner_tenant_uuid: owner_tenant_uuid})

    def update_remaining_owner_tenant_uuid(self, owner_tenant_uuid):
        with self.rw_session() as session:
            query = session.query(Subscription)
            query = query.filter(
                Subscription.owner_tenant_uuid == TO_MIGRATE_TENANT_UUID
            )
            query.update({Subscription.owner_tenant_uuid: owner_tenant_uuid})
