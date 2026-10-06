"""Add query indexes.

Revision ID: 004
Revises: 003
Create Date: 2026-10-02
"""

from alembic import op


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX ix_silver_rides_market_window
        ON silver_rides (market, data_window)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_fact_events_date_key
        ON fact_events (date_key)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_fact_events_date_key")
    op.execute("DROP INDEX ix_silver_rides_market_window")