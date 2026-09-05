import os
import sys
from datetime import date

import psycopg

from meridian.transform_to_gold.database import (
    delete_day,
    insert_date,
    insert_stations,
    insert_events,
)
from meridian.transform_to_gold.transform import build_date_row


def main() -> None:
    dataset, target_date = sys.argv[1:3]

    if dataset != "station-daily":
        raise ValueError(f"Unknown dataset: {dataset}")

    target = date.fromisoformat(target_date)

    database_url = os.environ["DATABASE_URL"]

    with psycopg.connect(database_url) as conn:
        delete_day(conn, target_date)

        date_row = build_date_row(target)
        insert_date(conn, date_row)

        insert_stations(conn, target_date)

        inserted_events = insert_events(
            conn,
            target_date,
        )

        conn.commit()

    # print("Gold transformation completed")
    # print(f"Date: {target_date}")
    # print(f"Inserted events: {inserted_events}")


if __name__ == "__main__":
    main()






# def main() -> None:
#     dataset, station_report, target_date = sys.argv[1:4]

#     if dataset != "station-daily":
#         raise ValueError(f"Unknown dataset: {dataset}")

#     market = station_report.upper()

#     target = date.fromisoformat(target_date)

#     database_url = os.environ["DATABASE_URL"]

#     with psycopg.connect(database_url) as conn:
#         delete_day(conn, market, target_date)

#         date_row = build_date_row(target)
#         insert_date(conn, date_row)

#         insert_stations(conn, market, target_date)

#         inserted_events = insert_events(
#             conn,
#             market,
#             target_date,
#         )

#         conn.commit()

#     print("Gold transformation completed")
#     print(f"Market: {market}")
#     print(f"Date: {target_date}")
#     print(f"Inserted events: {inserted_events}")


# if __name__ == "__main__":
#     main()