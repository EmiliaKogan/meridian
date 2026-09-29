"""create control table

Revision ID: 003
Revises: 002
Create Date: 2026-09-27 19:32:34.092486

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
    op.execute(
        """
        CREATE TABLE control_table (
            id BIGSERIAL PRIMARY KEY,
            layer TEXT NOT NULL
                CHECK (layer IN ('bronze', 'silver', 'gold')),
            job TEXT NOT NULL,
            market TEXT NOT NULL,
            load_window TEXT NOT NULL,
            status TEXT NOT NULL
                CHECK (status IN ('SUCCESS', 'FAILED')),
            finished_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )



def downgrade() -> None:
    op.execute(
        """
        DROP TABLE control_table
        """
    )