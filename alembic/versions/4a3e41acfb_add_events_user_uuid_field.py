"""add events_user_uuid field

Revision ID: 4a3e41acfb
Revises: 1495b7c1224

"""

# revision identifiers, used by Alembic.
revision = '4a3e41acfb'
down_revision = '1495b7c1224'

import sqlalchemy as sa

from alembic import op


def upgrade():
    op.add_column('webhookd_subscription', sa.Column('events_user_uuid', sa.String(36)))


def downgrade():
    op.drop_column('webhookd_subscription', 'events_user_uuid')
