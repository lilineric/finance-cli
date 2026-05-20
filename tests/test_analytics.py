from datetime import date

import pytest

from finance_cli.analytics import (
    calculate_percentile,
    parse_query_date,
    start_date_for_years,
    validate_years,
)


def test_calculate_percentile_uses_less_than_or_equal_formula():
    result = calculate_percentile([10.0, 20.0, 30.0], 20.0)

    assert result == pytest.approx(66.6666667)


def test_calculate_percentile_historical_max_is_100():
    result = calculate_percentile([10.0, 20.0, 30.0], 30.0)

    assert result == 100.0


def test_calculate_percentile_rejects_empty_values():
    with pytest.raises(ValueError, match="No values available"):
        calculate_percentile([], 30.0)


def test_parse_query_date_accepts_iso_date():
    assert parse_query_date("2026-04-20") == date(2026, 4, 20)


def test_parse_query_date_rejects_invalid_format():
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        parse_query_date("2026/04/20")


def test_validate_years_accepts_1_to_10():
    assert validate_years(1) == 1
    assert validate_years(10) == 10


def test_validate_years_rejects_out_of_range_values():
    with pytest.raises(ValueError, match="between 1 and 10"):
        validate_years(0)
    with pytest.raises(ValueError, match="between 1 and 10"):
        validate_years(11)


def test_start_date_for_years_handles_leap_day():
    assert start_date_for_years(date(2024, 2, 29), 1) == date(2023, 2, 28)
