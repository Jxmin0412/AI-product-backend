"""Add user_id to user_searches

Revision ID: a3b1c9d2e4f5
Revises: 2d0ca7f7425a
Create Date: 2026-02-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a3b1c9d2e4f5'
down_revision: Union[str, None] = '2d0ca7f7425a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add user_id column to user_searches table."""
    op.add_column(
        'user_searches',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        'fk_user_searches_user_id',
        'user_searches', 'users',
        ['user_id'], ['id']
    )
    op.create_index('ix_user_searches_user_id', 'user_searches', ['user_id'])


def downgrade() -> None:
    """Remove user_id column from user_searches table."""
    op.drop_index('ix_user_searches_user_id', table_name='user_searches')
    op.drop_constraint('fk_user_searches_user_id', 'user_searches', type_='foreignkey')
    op.drop_column('user_searches', 'user_id')
