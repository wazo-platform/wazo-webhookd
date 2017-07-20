"""create subscription tables

Revision ID: 1495b7c1224
Revises: None

"""

# revision identifiers, used by Alembic.
revision = '1495b7c1224'
down_revision = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.schema import Column


def upgrade():
    op.create_table(
        'webhookd_subscription',
        Column('uuid', sa.String(38),
               server_default=sa.text('uuid_generate_v4()'), primary_key=True),
        Column('name', sa.Text()),
        Column('service', sa.Text()),
    )
    op.create_table(
        'webhookd_subscription_event',
        Column('uuid', sa.String(38),
               server_default=sa.text('uuid_generate_v4()'), primary_key=True),
        Column('subscription_uuid', sa.String(38),
               sa.ForeignKey('webhookd_subscription.uuid', ondelete='CASCADE'),
               nullable=False),
        Column('event_name', sa.Text(), nullable=False),
        sa.UniqueConstraint('subscription_uuid', 'event_name'),
    )
    op.create_table(
        'webhookd_subscription_option',
        Column('uuid', sa.String(38),
               server_default=sa.text('uuid_generate_v4()'), primary_key=True),
        Column('subscription_uuid', sa.String(38),
               sa.ForeignKey('webhookd_subscription.uuid', ondelete='CASCADE'),
               nullable=False),
        Column('name', sa.Text(), nullable=False),
        Column('value', sa.Text()),
        sa.UniqueConstraint('subscription_uuid', 'name'),
    )


def downgrade():
    op.drop_constraint(u'webhookd_subscription_event_subscription_uuid_fkey', 'webhookd_subscription_event', type_='foreignkey')
    op.drop_constraint(u'webhookd_subscription_option_subscription_uuid_fkey', 'webhookd_subscription_option', type_='foreignkey')
    op.drop_table('webhookd_subscription')
    op.drop_table('webhookd_subscription_event')
    op.drop_table('webhookd_subscription_option')
