from datetime import date, datetime
from typing import Iterable


def parse_query_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Date must use YYYY-MM-DD format") from exc


def validate_years(years: int) -> int:
    if years < 1 or years > 10:
        raise ValueError("Years must be between 1 and 10")
    return years


def start_date_for_years(end_date: date, years: int) -> date:
    validate_years(years)
    try:
        return end_date.replace(year=end_date.year - years)
    except ValueError:
        return end_date.replace(year=end_date.year - years, day=28)


def calculate_percentile(values: Iterable[float], current_value: float) -> float:
    samples = list(values)
    if not samples:
        raise ValueError("No values available for percentile calculation")
    less_or_equal_count = sum(1 for value in samples if value <= current_value)
    return less_or_equal_count / len(samples) * 100
