"""add indices for foreign keys

Revision ID: 911ad0861ef5
Revises: f573303305e5

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = '911ad0861ef5'
down_revision = 'f573303305e5'


def upgrade():
    op.create_index(
        'webhookd_subscription_event__idx__subscription_uuid',
        'webhookd_subscription_event',
        ['subscription_uuid'],
    )
    op.create_index(
        'webhookd_subscription_option__idx__subscription_uuid',
        'webhookd_subscription_option',
        ['subscription_uuid'],
    )
    op.create_index(
        'webhookd_subscription_metadatum__idx__subscription_uuid',
        'webhookd_subscription_metadatum',
        ['subscription_uuid'],
    )
    op.create_index(
        'webhookd_subscription_log__idx__subscription_uuid',
        'webhookd_subscription_log',
        ['subscription_uuid'],
    )


def downgrade():
    op.drop_index('webhookd_subscription_metadatum__idx__subscription_uuid')
    op.drop_index('webhookd_subscription_log__idx__subscription_uuid')
    op.drop_index('webhookd_subscription_option__idx__subscription_uuid')
    op.drop_index('webhookd_subscription_event__idx__subscription_uuid')
