"""remove_unecessary_sequence

Revision ID: df313e703ee8
Revises: cab8bbbdcfae

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = 'df313e703ee8'
down_revision = 'cab8bbbdcfae'

seq = sa.Sequence('webhookd_subscription_log_attempts_seq')  # type: ignore


def upgrade():
    op.alter_column('webhookd_subscription_log', 'attempts', server_default=None)
    op.execute('DROP SEQUENCE IF EXISTS webhookd_subscription_log_attempts_seq;')


def downgrade():
    op.execute('CREATE SEQUENCE webhookd_subscription_log_attempts_seq;')
    op.alter_column(
        'webhookd_subscription_log', 'attempts', server_default=seq.next_value()
    )
