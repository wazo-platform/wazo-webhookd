"""squashed baseline wazo-25.14

Revision ID: 3eb8e3fa4537
Revises: None

"""

# revision identifiers, used by Alembic.
revision = '3eb8e3fa4537'
down_revision = None

import os

from alembic import op


def upgrade():
    # Read and execute the SQL dump file
    versions_dir_path = os.path.dirname(__file__)
    sql_file_path = os.path.join(versions_dir_path, 'baseline-2514.sql')

    with open(sql_file_path) as f:
        sql_content = f.read()

    # Execute the SQL content
    op.execute(sql_content)


def downgrade():
    pass
