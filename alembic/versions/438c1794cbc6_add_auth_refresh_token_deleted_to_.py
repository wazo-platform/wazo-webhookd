"""add auth_refresh_token_deleted to mobile subscriptions

Revision ID: 438c1794cbc6
Revises: 3eb8e3fa4537

"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from alembic import op

# revision identifiers, used by Alembic.
revision = '438c1794cbc6'
down_revision = '3eb8e3fa4537'


NEW_EVENT_NAME = 'auth_refresh_token_deleted'

subscription_table = sa.table(
    'webhookd_subscription',
    sa.column('uuid'),
    sa.column('service'),
)
subscription_metadatum_table = sa.table(
    'webhookd_subscription_metadatum',
    sa.column('uuid'),
    sa.column('subscription_uuid'),
    sa.column('key'),
    sa.column('value'),
)
subscription_event_table = sa.table(
    'webhookd_subscription_event',
    sa.column('subscription_uuid'),
    sa.column('event_name'),
)


def _mobile_subscriptions_select():
    return (
        sa.select([subscription_table.c.uuid])
        .select_from(
            subscription_table.join(
                subscription_metadatum_table,
                subscription_metadatum_table.c.subscription_uuid
                == subscription_table.c.uuid,
            )
        )
        .where(
            sa.and_(
                subscription_table.c.service == 'mobile',
                subscription_metadatum_table.c.key == 'mobile',
                subscription_metadatum_table.c.value == 'true',
            )
        )
    )


def upgrade():
    mobile_subscriptions = (
        sa.select(
            [
                subscription_table.c.uuid.label('subscription_uuid'),
                sa.literal(NEW_EVENT_NAME).label('event_name'),
            ]
        )
        .select_from(
            subscription_table.join(
                subscription_metadatum_table,
                subscription_metadatum_table.c.subscription_uuid
                == subscription_table.c.uuid,
            )
        )
        .where(
            sa.and_(
                subscription_table.c.service == 'mobile',
                subscription_metadatum_table.c.key == 'mobile',
                subscription_metadatum_table.c.value == 'true',
            )
        )
    )

    insert_stmt = (
        insert(subscription_event_table)
        .from_select(['subscription_uuid', 'event_name'], mobile_subscriptions)
        .on_conflict_do_nothing(index_elements=['subscription_uuid', 'event_name'])
    )
    op.execute(insert_stmt)


def downgrade():
    delete_stmt = subscription_event_table.delete().where(
        sa.and_(
            subscription_event_table.c.event_name == NEW_EVENT_NAME,
            subscription_event_table.c.subscription_uuid.in_(
                _mobile_subscriptions_select()
            ),
        )
    )
    op.execute(delete_stmt)
