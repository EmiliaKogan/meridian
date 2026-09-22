def record_load(conn, job: str, market: str, window: str) -> None:
    """Record a successfully completed operational load."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO operational_loads (job, market, load_window)
            VALUES (%s, %s, %s)
            ON CONFLICT (job, market, load_window)
            DO UPDATE SET loaded_at = CURRENT_TIMESTAMP
            """, ##ON CONFLICT (job, market, load_window) DO NOTHING
            (job, market, window),
        )