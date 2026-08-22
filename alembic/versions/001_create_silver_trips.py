"""create silver trips

Revision ID: 001
Revises: 
Create Date: 2026-08-22 10:20:25.007954

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the silver rides table."""
    op.execute("""
        CREATE TABLE silver_rides (
            ride_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            market TEXT NOT NULL,
            started_at TIMESTAMPTZ NOT NULL,
            ended_at TIMESTAMPTZ NOT NULL,
            start_station_id TEXT NOT NULL,
            end_station_id TEXT NOT NULL,
            start_station_name TEXT,
            end_station_name TEXT,
            start_lat DOUBLE PRECISION,
            start_lng DOUBLE PRECISION,
            end_lat DOUBLE PRECISION,
            end_lng DOUBLE PRECISION
        );
    """)


def downgrade() -> None:
    """Drop the silver rides table."""
    op.execute("DROP TABLE silver_rides;")
