"""create operational loads

Revision ID: 003
Revises: 002
Create Date: 2026-09-21 15:04:24.696674

"""
from typing import Sequence, Union

from alembic import op
# import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, Sequence[str], None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the operational load control table."""
    op.execute(
        """
        CREATE TABLE operational_loads (
            job TEXT NOT NULL,
            market TEXT NOT NULL,
            load_window TEXT NOT NULL,
            loaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (job, market, load_window)
        )
        """
    )


def downgrade() -> None:
    """Drop the operational load control table."""
    op.execute(
        """
        DROP TABLE operational_loads
        """
    )