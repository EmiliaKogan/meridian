from datetime import date


def build_date_row(target_date: date) -> dict:
    return {
        "date_key": int(target_date.strftime("%Y%m%d")),
        "date": target_date,
        "year": target_date.year,
        "month": target_date.month,
        "day": target_date.day,
    }