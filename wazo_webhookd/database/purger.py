# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import datetime

from sqlalchemy import func

from .models import SubscriptionLog


class SubscriptionLogsPurger:
    def purge(self, days_to_keep, session):
        query = SubscriptionLog.__table__.delete().where(
            SubscriptionLog.started_at
            < (func.localtimestamp() - datetime.timedelta(days=days_to_keep))
        )
        session.execute(query)
