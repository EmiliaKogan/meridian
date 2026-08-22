"""create silver trips

Revision ID: 001
Revises: 
Create Date: 2026-08-22 10:20:25.007954

"""

from typing import Sequence, Union

from alembic import op


revision: str = "001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the Silver tables."""

    op.execute("""
        CREATE TABLE silver_rides (
            ride_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            market TEXT NOT NULL,
            data_window TEXT NOT NULL,
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

    op.execute("""
        CREATE TABLE silver_rejects (
            reject_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            market TEXT NOT NULL,
            data_window TEXT NOT NULL,
            started_at TIMESTAMPTZ,
            ended_at TIMESTAMPTZ,
            start_station_id TEXT,
            end_station_id TEXT,
            start_station_name TEXT,
            end_station_name TEXT,
            start_lat DOUBLE PRECISION,
            start_lng DOUBLE PRECISION,
            end_lat DOUBLE PRECISION,
            end_lng DOUBLE PRECISION,
            reason TEXT NOT NULL
        );
    """)


def downgrade() -> None:
    """Drop the Silver tables."""

    op.execute("DROP TABLE IF EXISTS silver_rejects;")
    op.execute("DROP TABLE IF EXISTS silver_rides;")