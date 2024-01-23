"""add_hook_log_table

Revision ID: cab8bbbdcfae
Revises: f63e43dcf0ca

"""

# revision identifiers, used by Alembic.
revision = 'cab8bbbdcfae'
down_revision = 'f63e43dcf0ca'

import sqlalchemy as sa
from sqlalchemy.schema import Column
from sqlalchemy_utils import JSONType

from alembic import op


def upgrade():
    op.create_table(
        'webhookd_subscription_log',
        Column('uuid', sa.String(36), primary_key=True),
        Column(
            'subscription_uuid',
            sa.String(38),
            sa.ForeignKey('webhookd_subscription.uuid', ondelete='CASCADE'),
            nullable=False,
        ),
        Column("status", sa.Enum("success", "failure", "error", name='status_types')),
        Column('started_at', sa.DateTime(timezone=True)),
        Column('ended_at', sa.DateTime(timezone=True)),
        Column('attempts', sa.Integer(), primary_key=True),
        Column('max_attempts', sa.Integer()),
        Column('event', JSONType),
        Column('detail', JSONType),
    )


def downgrade():
    op.drop_table('webhookd_subscription_log')
    op.execute('DROP TYPE status_types')
