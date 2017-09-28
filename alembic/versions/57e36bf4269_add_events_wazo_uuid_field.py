"""add events_wazo_uuid field

Revision ID: 57e36bf4269
Revises: 231d4dbd38

"""

# revision identifiers, used by Alembic.
revision = '57e36bf4269'
down_revision = '231d4dbd38'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('webhookd_subscription', sa.Column('events_wazo_uuid', sa.String(36)))


def downgrade():
    op.drop_column('webhookd_subscription', 'events_wazo_uuid')
