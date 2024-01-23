"""add user_uuid field to subscriptions

Revision ID: 231d4dbd38
Revises: 4a3e41acfb

"""

# revision identifiers, used by Alembic.
revision = '231d4dbd38'
down_revision = '4a3e41acfb'

import sqlalchemy as sa

from alembic import op


def upgrade():
    op.add_column('webhookd_subscription', sa.Column('owner_user_uuid', sa.String(36)))


def downgrade():
    op.drop_column('webhookd_subscription', 'owner_user_uuid')
