"""add_hook_log_table

Revision ID: cab8bbbdcfae
Revises: f63e43dcf0ca

"""

# revision identifiers, used by Alembic.
revision = 'cab8bbbdcfae'
down_revision = 'f63e43dcf0ca'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.schema import Column
from sqlalchemy_utils import JSONType


def upgrade():
    op.create_table(
        'webhookd_subscription_hook_log',
        Column('uuid', sa.String(38),
               server_default=sa.text('uuid_generate_v4()'), primary_key=True),
        Column('subscription_uuid', sa.String(38),
               sa.ForeignKey('webhookd_subscription.uuid', ondelete='CASCADE'),
               nullable=False),
        Column("status", sa.Enum("success", "failure", "fatal",
                                 name='status_types')),
        Column('started_at', sa.DateTime(timezone=True)),
        Column('ended_at', sa.DateTime(timezone=True)),
        Column('tries', sa.Integer()),
        Column('detail', JSONType)
    )


def downgrade():
    op.drop_table('webhookd_subscription_hook_log')
    op.execute('DROP TYPE status_types')
