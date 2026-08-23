"""Create gold tables.


Revision ID: 002
Revises: 
Create Date: 2026-08-23

"""

from alembic import op


revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE dim_date (
            date_key INTEGER PRIMARY KEY,
            date DATE NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            day INTEGER NOT NULL
        )
        """
    )

    op.execute(
        """
        CREATE TABLE dim_station (
            market TEXT NOT NULL,
            station_id TEXT NOT NULL,
            station_name TEXT,
            PRIMARY KEY (market, station_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE fact_events (
            event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            ride_id BIGINT NOT NULL,
            market TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_timestamp TIMESTAMPTZ NOT NULL,
            station_id TEXT NOT NULL,
            date_key INTEGER NOT NULL,

            FOREIGN KEY (date_key)
                REFERENCES dim_date(date_key),

            FOREIGN KEY (market, station_id)
                REFERENCES dim_station(market, station_id)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE fact_events")
    op.execute("DROP TABLE dim_station")
    op.execute("DROP TABLE dim_date")