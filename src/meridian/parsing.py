def parse_dataset_market(value: str) -> tuple[str, str]:
    dataset, market = value.split(":", 1)

    if dataset != "trips":
        raise ValueError(f"Unknown dataset: {dataset}")

    market = market.upper()
    if market not in {"NYC", "JC"}:
        raise ValueError(f"Unknown market: {market}")

    return dataset, market


def parse_month(value: str) -> str:
    try:
        year, month = map(int, value.split("-"))
        valid = len(value) == 7 and value[4] == "-"
        valid &= year >= 1 and 1 <= month <= 12
    except ValueError:
        valid = False

    if not valid:
        raise ValueError(f"Invalid month: {value}")

    return value