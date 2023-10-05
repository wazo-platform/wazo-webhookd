"""add-cancel-dial-mobile-to-current-subscriptions

Revision ID: f573303305e5
Revises: df313e703ee8

"""

# revision identifiers, used by Alembic.
revision = 'f573303305e5'
down_revision = 'df313e703ee8'

from alembic import op
import sqlalchemy as sa

NEW_EVENT_NAME = 'call_cancel_push_notification'

subscription_tbl = sa.sql.table(
    'webhookd_subscription',
    sa.sql.column('uuid'),
    sa.sql.column('service'),
)
subscription_event_tbl = sa.sql.table(
    'webhookd_subscription_event',
    sa.sql.column('subscription_uuid'),
    sa.sql.column('event_name'),
)


def upgrade():
    subscription_uuids = set()

    query = subscription_tbl.select().where(subscription_tbl.c.service == 'mobile')
    for subscription in op.get_bind().execute(query):
        subscription_uuids.add(subscription.uuid)

    query = subscription_event_tbl.select().where(
        subscription_event_tbl.c.event_name == NEW_EVENT_NAME
    )
    for subscription_event in op.get_bind().execute(query):
        subscription_uuids.discard(subscription_event.subscription_uuid)

    for subscription_uuid in subscription_uuids:
        values_query = subscription_event_tbl.insert().values(
            subscription_uuid=subscription_uuid,
            event_name=NEW_EVENT_NAME,
        )
        op.get_bind().execute(values_query)


def downgrade():
    query = subscription_event_tbl.delete().where(
        subscription_event_tbl.c.event_name == NEW_EVENT_NAME
    )
    op.execute(query)
