"""add tenant to subscription

Revision ID: f63e43dcf0ca
Revises: 35b30e165f6

"""

# revision identifiers, used by Alembic.
revision = 'f63e43dcf0ca'
down_revision = '35b30e165f6'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(
        'webhookd_subscription',
        sa.Column(
            'owner_tenant_uuid',
            sa.String(36),
            nullable=False,
            server_default='00000000-0000-0000-0000-000000000000',
        ),
    )
    op.alter_column('webhookd_subscription', 'owner_tenant_uuid', server_default=None)


def downgrade():
    op.drop_column('webhookd_subscription', 'owner_tenant_uuid')
