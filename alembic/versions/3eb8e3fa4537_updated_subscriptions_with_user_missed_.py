"""Updated subscriptions with user_missed_call event

Revision ID: 3eb8e3fa4537
Revises: 911ad0861ef5

"""

# revision identifiers, used by Alembic.
revision = '3eb8e3fa4537'
down_revision = '911ad0861ef5'

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from alembic import op

subscription_table = sa.table(
    'webhookd_subscription',
    sa.column('uuid'),
    sa.column('service'),
)

subscription_event_table = sa.table(
    'webhookd_subscription_event',
    sa.column('subscription_uuid'),
    sa.column('event_name'),
)


def upgrade():
    mobile_subscriptions = sa.select(
        [
            subscription_table.c.uuid.label('subscription_uuid'),
            sa.literal('user_missed_call').label('event_name'),
        ]
    ).where(subscription_table.c.service == 'mobile')

    insert_stmt = (
        insert(subscription_event_table)
        .from_select(['subscription_uuid', 'event_name'], mobile_subscriptions)
        .on_conflict_do_nothing(index_elements=['subscription_uuid', 'event_name'])
    )
    op.execute(insert_stmt)


def downgrade():
    delete_stmt = subscription_event_table.delete().where(
        sa.and_(
            subscription_event_table.c.event_name == 'user_missed_call',
            subscription_event_table.c.subscription_uuid.in_(
                sa.select([subscription_table.c.uuid]).where(
                    subscription_table.c.service == 'mobile'
                )
            ),
        )
    )
    op.execute(delete_stmt)
