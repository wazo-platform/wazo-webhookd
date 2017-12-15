"""add subscriptions metadata table

Revision ID: 35b30e165f6
Revises: 57e36bf4269

"""

# revision identifiers, used by Alembic.
revision = '35b30e165f6'
down_revision = '57e36bf4269'

import sqlalchemy as sa

from alembic import op
from sqlalchemy.schema import Column


def upgrade():
    op.create_table(
        'webhookd_subscription_metadatum',
        Column('uuid', sa.String(38),
               server_default=sa.text('uuid_generate_v4()'), primary_key=True),
        Column('subscription_uuid', sa.String(38),
               sa.ForeignKey('webhookd_subscription.uuid', ondelete='CASCADE'),
               nullable=False),
        Column('key', sa.Text(), nullable=False),
        Column('value', sa.Text()),
    )


def downgrade():
    op.drop_table('webhookd_subscription_metadatum')
