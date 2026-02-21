"""Add results_data to user_searches

Revision ID: b4c2d3e5f6a7
Revises: a3b1c9d2e4f5
Create Date: 2026-02-21 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b4c2d3e5f6a7'
down_revision: Union[str, None] = 'a3b1c9d2e4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add results_data JSONB column to store search results for cross-user recommendations."""
    op.add_column(
        'user_searches',
        sa.Column('results_data', postgresql.JSONB(), nullable=True)
    )


def downgrade() -> None:
    """Remove results_data column."""
    op.drop_column('user_searches', 'results_data')
