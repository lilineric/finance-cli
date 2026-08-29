from datetime import UTC, date, datetime
from enum import Enum
import json
from pathlib import Path
import sys
from typing import Annotated

import click
import typer
from typer.core import TyperGroup

from finance_cli.analytics import parse_query_date, validate_years
from finance_cli.config import load_config
from finance_cli.db import FundInfo, MetricsRepository, OperationFee, SQLiteApiError
from finance_cli.output import (
    format_fund_info_json,
    format_fund_info_text,
    format_json,
    format_money_fund_json,
    format_money_fund_range_json,
    format_money_fund_range_text,
    format_money_fund_text,
    format_range_json,
    format_range_text,
    format_text,
)
from finance_cli.service import (
    MetricsService,
    MoneyFundQueryResult,
    MoneyFundRangeQueryResult,
)
from finance_cli.sources import (
    DataSourceError,
    MONEY_FUND_ANNUALIZED_YIELD_METRIC,
    MONEY_FUND_INCOME_METRIC,
    compute_dividend_yield_spread_rows,
    compute_erp_rows,
    compute_gold_m2_ratio_rows,
    fetch_cn10y_yield_rows,
    fetch_dividend_yield_spread_rows,
    fetch_erp_rows,
    fetch_fund_info,
    fetch_money_fund_rows,
    fetch_gold_rows,
    fetch_gold_m2_ratio_rows,
    fetch_gold_usd_rows,
    fetch_fund_nav_rows,
    fetch_index_dividend_yield_rows,
    fetch_index_value_rows,
    fetch_index_pb_rows,
    fetch_index_pe_rows,
    fetch_m2_rows,
    fetch_us10y_tips_yield_rows,
    normalize_index_pe_code,
    normalize_index_value_code,
    normalize_csindex_code,
    fetch_sw_index_pb_rows,
    normalize_fund_code,
)


class JsonClickException(click.ClickException):
    def __init__(self, error_code: str, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.exit_code = exit_code


class JsonErrorGroup(TyperGroup):
    def main(
        self,
        args: list[str] | None = None,
        prog_name: str | None = None,
        complete_var: str | None = None,
        standalone_mode: bool = True,
        **extra: object,
    ) -> object:
        current_args = list(sys.argv[1:] if args is None else args)
        wants_json = "--json" in current_args
        try:
            return super().main(
                args=args,
                prog_name=prog_name,
                complete_var=complete_var,
                standalone_mode=False,
                **extra,
            )
        except click.ClickException as exc:
            if wants_json:
                click.echo(_format_error_json(exc))
            else:
                exc.show()
            if standalone_mode:
                raise SystemExit(exc.exit_code) from exc
            if wants_json:
                return exc.exit_code
            raise


app = typer.Typer(help="Financial data CLI", cls=JsonErrorGroup)
sync_app = typer.Typer(help="Synchronize local data")
app.add_typer(sync_app, name="sync")
SW_INDEX_CATEGORIES = ("市场表征", "一级行业", "二级行业", "风格指数")
FUND_INFO_FIELDS = {
    "code",
    "name",
    "fund_type",
    "established_date",
    "asset_size",
    "operation_fee",
    "purchase_status",
    "purchase_limit_amount",
    "redemption_status",
    "morningstar_rating",
    "purchase_fee",
    "redemption_fee",
    "source",
    "updated_at",
}
OPERATION_FEE_FIELDS = {
    "total",
    "management_fee",
    "custodian_fee",
    "sales_service_fee",
}
PURCHASE_FEE_FIELDS = {
    "min_amount",
    "max_amount",
    "original_rate",
    "discounted_rate",
    "fixed_fee",
}
REDEMPTION_FEE_FIELDS = {
    "min_holding_days",
    "max_holding_days",
    "original_rate",
    "discounted_rate",
    "fixed_fee",
}


class FundNavType(str, Enum):
    unit = "unit"
    accumulated = "accumulated"


def _service() -> MetricsService:
    config = load_config()
    return MetricsService(MetricsRepository(config.sqlite_api_host, config.sqlite_db))


def _format_error_json(exc: click.ClickException) -> str:
    error_code = getattr(exc, "error_code", None) or _default_error_code(exc)
    return json.dumps(
        {"error": {"code": error_code, "message": exc.format_message()}},
        ensure_ascii=False,
    )


def _default_error_code(exc: click.ClickException) -> str:
    if isinstance(exc, click.UsageError):
        return "invalid_parameter"
    return "runtime_error"


def _runtime_click_exception(exc: DataSourceError | SQLiteApiError) -> JsonClickException:
    if isinstance(exc, SQLiteApiError):
        return JsonClickException("sqlite_api_error", str(exc))
    message = str(exc)
    if message.startswith("Invalid ") or message.startswith("PB without --category"):
        return JsonClickException("invalid_parameter", message)
    return JsonClickException("runtime_error", message)


def _value_click_exception(exc: ValueError) -> JsonClickException:
    message = str(exc)
    if (
        message.startswith("Years must")
        or message.startswith("category must")
        or message == "from date must be on or before to date"
        or message == "Date must use YYYY-MM-DD format"
    ):
        return JsonClickException("invalid_parameter", message, exit_code=2)
    return JsonClickException("runtime_error", message)


def _is_range_mode(from_date: str | None, to_date: str | None) -> bool:
    return from_date is not None or to_date is not None


def _validate_range_options(
    from_date: str | None,
    to_date: str | None,
    query_date: str | None,
    years: int | None = None,
) -> tuple[str, str]:
    if from_date is None or to_date is None:
        raise JsonClickException("invalid_parameter", "--from and --to must be supplied together", exit_code=2)
    if query_date is not None:
        raise JsonClickException("invalid_parameter", "--date cannot be used with --from/--to", exit_code=2)
    if years is not None:
        raise JsonClickException("invalid_parameter", "--years cannot be used with --from/--to", exit_code=2)
    return from_date, to_date


def _default_query_date(query_date: str | None) -> str:
    return query_date or date.today().isoformat()


def _default_years(years: int | None) -> int:
    return 10 if years is None else years


def _is_missing_fund_nav_trend_error(exc: DataSourceError) -> bool:
    message = str(exc)
    return (
        "Data_netWorthTrend is not defined" in message
        or "Data_ACWorthTrend is not defined" in message
        or "is a money fund; NAV trend data is unavailable" in message
    )


def _query_money_fund_value(
    service: MetricsService,
    code: str,
    requested_date: str,
) -> MoneyFundQueryResult:
    fetch_missing = lambda: fetch_money_fund_rows(code)
    income = service.query_value(
        "fund",
        code,
        MONEY_FUND_INCOME_METRIC,
        requested_date,
        fetch_missing,
    )
    annualized_yield = service.query_value(
        "fund",
        code,
        MONEY_FUND_ANNUALIZED_YIELD_METRIC,
        requested_date,
        fetch_missing,
    )
    if income.actual_date != annualized_yield.actual_date:
        raise ValueError(f"No complete money fund data available for fund {code} on {requested_date}")
    return MoneyFundQueryResult(
        asset_type="fund",
        code=code,
        fund_type="货币基金",
        requested_date=income.requested_date,
        actual_date=income.actual_date,
        metrics={
            MONEY_FUND_INCOME_METRIC: income.value,
            MONEY_FUND_ANNUALIZED_YIELD_METRIC: annualized_yield.value,
        },
        source=income.source,
        stale=income.stale or annualized_yield.stale,
    )


def _query_money_fund_range(
    service: MetricsService,
    code: str,
    requested_from: str,
    requested_to: str,
) -> MoneyFundRangeQueryResult:
    fetch_missing = lambda: fetch_money_fund_rows(code)
    income = service.query_range(
        "fund",
        code,
        MONEY_FUND_INCOME_METRIC,
        requested_from,
        requested_to,
        fetch_missing,
    )
    annualized_yield = service.query_range(
        "fund",
        code,
        MONEY_FUND_ANNUALIZED_YIELD_METRIC,
        requested_from,
        requested_to,
        fetch_missing,
    )
    income_by_date = {row_date: (value, source) for row_date, value, source in income.data}
    annualized_yield_by_date = {
        row_date: value for row_date, value, _source in annualized_yield.data
    }
    dates = sorted(set(income_by_date) & set(annualized_yield_by_date))
    if not dates:
        raise ValueError(
            f"No complete money fund data available for fund {code} between {requested_from} and {requested_to}"
        )
    data = [
        (
            row_date,
            {
                MONEY_FUND_INCOME_METRIC: income_by_date[row_date][0],
                MONEY_FUND_ANNUALIZED_YIELD_METRIC: annualized_yield_by_date[row_date],
            },
            income_by_date[row_date][1],
        )
        for row_date in dates
    ]
    return MoneyFundRangeQueryResult(
        asset_type="fund",
        code=code,
        fund_type="货币基金",
        requested_from=income.requested_from,
        requested_to=income.requested_to,
        actual_start_date=dates[0],
        actual_end_date=dates[-1],
        data=data,
        stale=income.stale or annualized_yield.stale,
    )


def _load_fund_info_payload(data: str | None, data_file: str | None) -> dict[str, object]:
    if data is not None and data_file is not None:
        raise JsonClickException(
            "invalid_parameter",
            "--data and --data-file cannot be used together",
            exit_code=2,
        )
    if data is None and data_file is None:
        raise JsonClickException(
            "invalid_parameter",
            "one of --data or --data-file is required",
            exit_code=2,
        )
    try:
        raw = data if data is not None else Path(str(data_file)).read_text(encoding="utf-8")
        payload = json.loads(raw)
    except OSError as exc:
        raise JsonClickException("invalid_parameter", f"failed to read --data-file: {exc}", exit_code=2) from exc
    except json.JSONDecodeError as exc:
        raise JsonClickException("invalid_parameter", f"invalid JSON: {exc.msg}", exit_code=2) from exc
    if not isinstance(payload, dict):
        raise JsonClickException("invalid_parameter", "fund info JSON must be an object", exit_code=2)
    return payload


def _fund_info_from_payload(code: str, payload: dict[str, object]) -> FundInfo:
    unknown_fields = set(payload) - FUND_INFO_FIELDS
    if unknown_fields:
        names = ", ".join(sorted(unknown_fields))
        raise JsonClickException("invalid_parameter", f"Unknown fund info fields: {names}", exit_code=2)
    payload_code = payload.get("code")
    if payload_code is not None and str(payload_code) != code:
        raise JsonClickException("invalid_parameter", "JSON code must match --code", exit_code=2)
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise JsonClickException("invalid_parameter", "name is required", exit_code=2)
    source = payload.get("source", "manual")
    if not isinstance(source, str) or not source.strip():
        raise JsonClickException("invalid_parameter", "source must be a non-empty string", exit_code=2)
    updated_at = payload.get("updated_at") or datetime.now(UTC).isoformat()
    if not isinstance(updated_at, str) or not updated_at.strip():
        raise JsonClickException("invalid_parameter", "updated_at must be a string", exit_code=2)
    purchase_fee = _validate_fee_list(payload.get("purchase_fee", []), PURCHASE_FEE_FIELDS, "purchase_fee")
    redemption_fee = _validate_fee_list(payload.get("redemption_fee", []), REDEMPTION_FEE_FIELDS, "redemption_fee")
    purchase_limit_amount = _validate_purchase_limit_amount(payload.get("purchase_limit_amount", 0))
    operation_fee = _validate_operation_fee(payload.get("operation_fee", {}))
    return FundInfo(
        code=code,
        name=name.strip(),
        fund_type=_optional_payload_str(payload.get("fund_type")),
        established_date=_optional_payload_str(payload.get("established_date")),
        asset_size=_optional_payload_str(payload.get("asset_size")),
        operation_fee=operation_fee,
        purchase_status=_optional_payload_str(payload.get("purchase_status")),
        purchase_limit_amount=purchase_limit_amount,
        redemption_status=_optional_payload_str(payload.get("redemption_status")),
        morningstar_rating=_optional_payload_str(payload.get("morningstar_rating")),
        purchase_fee=purchase_fee,
        redemption_fee=redemption_fee,
        source=source.strip(),
        updated_at=updated_at.strip(),
    )


def _validate_operation_fee(value: object) -> OperationFee:
    if value is None:
        return OperationFee()
    if not isinstance(value, dict):
        raise JsonClickException("invalid_parameter", "operation_fee must be an object or null", exit_code=2)
    unknown_fields = set(value) - OPERATION_FEE_FIELDS
    if unknown_fields:
        names = ", ".join(sorted(unknown_fields))
        raise JsonClickException("invalid_parameter", f"Unknown operation_fee fields: {names}", exit_code=2)
    for field in OPERATION_FEE_FIELDS:
        if field in value:
            _require_optional_number(value, field, "operation_fee")
    return OperationFee(
        management_fee=_optional_payload_float(value.get("management_fee")),
        custodian_fee=_optional_payload_float(value.get("custodian_fee")),
        sales_service_fee=_optional_payload_float(value.get("sales_service_fee")),
    )


def _validate_fee_list(value: object, allowed_fields: set[str], field_name: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise JsonClickException("invalid_parameter", f"{field_name} must be a list", exit_code=2)
    result = []
    for item in value:
        if not isinstance(item, dict):
            raise JsonClickException("invalid_parameter", f"{field_name} items must be objects", exit_code=2)
        unknown_fields = set(item) - allowed_fields
        if unknown_fields:
            names = ", ".join(sorted(unknown_fields))
            raise JsonClickException("invalid_parameter", f"Unknown {field_name} fields: {names}", exit_code=2)
        tier = dict(item)
        if field_name == "purchase_fee":
            _validate_purchase_fee_tier(tier)
        else:
            _validate_redemption_fee_tier(tier)
        result.append(tier)
    return result


def _validate_purchase_limit_amount(value: object) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise JsonClickException("invalid_parameter", "purchase_limit_amount must be a number", exit_code=2)
    return float(value)


def _optional_payload_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _validate_purchase_fee_tier(tier: dict[str, object]) -> None:
    _require_number(tier, "min_amount", "purchase_fee")
    _require_optional_number(tier, "max_amount", "purchase_fee")
    _require_optional_number(tier, "original_rate", "purchase_fee")
    _require_optional_number(tier, "discounted_rate", "purchase_fee")
    if "fixed_fee" in tier:
        _require_optional_number(tier, "fixed_fee", "purchase_fee")


def _validate_redemption_fee_tier(tier: dict[str, object]) -> None:
    _require_number(tier, "min_holding_days", "redemption_fee")
    _require_optional_number(tier, "max_holding_days", "redemption_fee")
    _require_optional_number(tier, "original_rate", "redemption_fee")
    _require_optional_number(tier, "discounted_rate", "redemption_fee")
    if "fixed_fee" in tier:
        _require_optional_number(tier, "fixed_fee", "redemption_fee")


def _require_number(tier: dict[str, object], field: str, fee_name: str) -> None:
    value = tier.get(field)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise JsonClickException("invalid_parameter", f"{fee_name} {field} must be a number", exit_code=2)


def _require_optional_number(tier: dict[str, object], field: str, fee_name: str) -> None:
    value = tier.get(field)
    if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool)):
        raise JsonClickException("invalid_parameter", f"{fee_name} {field} must be a number or null", exit_code=2)


def _optional_payload_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise JsonClickException("invalid_parameter", "optional fund info fields must be strings or null", exit_code=2)
    return value


@app.command()
def pe(
    query_date: Annotated[str | None, typer.Option("--date")] = None,
    code: str = typer.Option(..., "--code"),
    years: int | None = typer.Option(None, "--years"),
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query index rolling PE percentile."""
    try:
        normalized_code = normalize_index_pe_code(code)
        if _is_range_mode(from_date, to_date):
            requested_from, requested_to = _validate_range_options(from_date, to_date, query_date, years)
            result = _service().query_range(
                "index",
                normalized_code,
                "rolling_pe",
                requested_from,
                requested_to,
                lambda: fetch_index_pe_rows(normalized_code),
            )
            typer.echo(format_range_json(result) if json_output else format_range_text(result))
            return

        query_date = _default_query_date(query_date)
        years = _default_years(years)
        validate_years(years)
        result = _service().query(
            "index",
            normalized_code,
            "rolling_pe",
            query_date,
            years,
            lambda: fetch_index_pe_rows(normalized_code),
            ensure_lookback_coverage=True,
            minimum_lookback_years=3,
        )
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(format_json(result) if json_output else format_text(result))


@app.command("dividend-yield")
def dividend_yield(
    query_date: Annotated[str | None, typer.Option("--date")] = None,
    code: str = typer.Option(..., "--code"),
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query index dividend-yield value."""
    try:
        normalized_code = normalize_csindex_code(code)
        if _is_range_mode(from_date, to_date):
            requested_from, requested_to = _validate_range_options(from_date, to_date, query_date)
            result = _service().query_range(
                "index",
                normalized_code,
                "dividend_yield",
                requested_from,
                requested_to,
                lambda: fetch_index_dividend_yield_rows(normalized_code),
            )
            typer.echo(format_range_json(result) if json_output else format_range_text(result))
            return

        query_date = _default_query_date(query_date)
        result = _service().query_value(
            "index",
            normalized_code,
            "dividend_yield",
            query_date,
            lambda: fetch_index_dividend_yield_rows(normalized_code, query_date=query_date),
        )
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(format_json(result) if json_output else format_text(result))


@app.command("index")
def index_value(
    query_date: Annotated[str | None, typer.Option("--date")] = None,
    code: str = typer.Option(..., "--code"),
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query index value."""
    try:
        normalized_code = normalize_index_value_code(code)
        if _is_range_mode(from_date, to_date):
            requested_from, requested_to = _validate_range_options(from_date, to_date, query_date)
            result = _service().query_range(
                "index",
                normalized_code,
                "price_index",
                requested_from,
                requested_to,
                lambda: fetch_index_value_rows(normalized_code),
            )
            typer.echo(format_range_json(result) if json_output else format_range_text(result))
            return

        query_date = _default_query_date(query_date)
        result = _service().query_value(
            "index",
            normalized_code,
            "price_index",
            query_date,
            lambda: fetch_index_value_rows(normalized_code),
        )
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(format_json(result) if json_output else format_text(result))


@app.command("fund-info")
def fund_info(
    code: str = typer.Option(..., "--code"),
    refresh: bool = typer.Option(False, "--refresh"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query fund profile, fees, purchase status, and rating."""
    try:
        normalized_code = normalize_fund_code(code)
        result = _service().query_fund_info(
            normalized_code,
            lambda: fetch_fund_info(normalized_code),
            refresh=refresh,
        )
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(format_fund_info_json(result) if json_output else format_fund_info_text(result))


@app.command("fund-info-update")
def fund_info_update(
    code: str = typer.Option(..., "--code"),
    data: str | None = typer.Option(None, "--data"),
    data_file: str | None = typer.Option(None, "--data-file"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Manually update fund profile data from JSON."""
    try:
        normalized_code = normalize_fund_code(code)
        payload = _load_fund_info_payload(data, data_file)
        fund_info = _fund_info_from_payload(normalized_code, payload)
        result = _service().update_fund_info(fund_info)
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except JsonClickException:
        raise
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(format_fund_info_json(result) if json_output else format_fund_info_text(result))


@app.command("fund-nav")
def fund_nav(
    query_date: Annotated[str | None, typer.Option("--date")] = None,
    code: str = typer.Option(..., "--code"),
    nav_type: FundNavType = typer.Option(
        FundNavType.unit,
        "--nav-type",
        help="NAV type to query: unit or accumulated. Defaults to unit.",
    ),
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query fund net asset value."""
    metric = "unit_nav" if nav_type == FundNavType.unit else "accumulated_nav"
    try:
        normalized_code = normalize_fund_code(code)
        service = _service()
        if _is_range_mode(from_date, to_date):
            requested_from, requested_to = _validate_range_options(from_date, to_date, query_date)
            try:
                result = service.query_range(
                    "fund",
                    normalized_code,
                    metric,
                    requested_from,
                    requested_to,
                    lambda: fetch_fund_nav_rows(normalized_code, nav_type=nav_type.value),
                )
                typer.echo(format_range_json(result) if json_output else format_range_text(result))
            except DataSourceError as exc:
                if not _is_missing_fund_nav_trend_error(exc):
                    raise
                money_fund_result = _query_money_fund_range(
                    service,
                    normalized_code,
                    requested_from,
                    requested_to,
                )
                typer.echo(
                    format_money_fund_range_json(money_fund_result)
                    if json_output
                    else format_money_fund_range_text(money_fund_result)
                )
            return

        query_date = _default_query_date(query_date)
        try:
            result = service.query_value(
                "fund",
                normalized_code,
                metric,
                query_date,
                lambda: fetch_fund_nav_rows(normalized_code, nav_type=nav_type.value),
            )
            typer.echo(format_json(result) if json_output else format_text(result))
        except DataSourceError as exc:
            if not _is_missing_fund_nav_trend_error(exc):
                raise
            money_fund_result = _query_money_fund_value(service, normalized_code, query_date)
            typer.echo(
                format_money_fund_json(money_fund_result)
                if json_output
                else format_money_fund_text(money_fund_result)
            )
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc


@app.command()
def pb(
    query_date: Annotated[str | None, typer.Option("--date")] = None,
    code: str = typer.Option(..., "--code"),
    category: str | None = typer.Option(None, "--category"),
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query index PB value."""
    try:
        if _is_range_mode(from_date, to_date):
            requested_from, requested_to = _validate_range_options(from_date, to_date, query_date)
            if category is None:
                result = _service().query_range(
                    "index",
                    code,
                    "pb",
                    requested_from,
                    requested_to,
                    lambda: fetch_index_pb_rows(code),
                )
            else:
                _validate_sw_category(category)
                result = _service().query_range(
                    f"sw_index:{category}",
                    code,
                    "pb",
                    requested_from,
                    requested_to,
                    lambda: fetch_sw_index_pb_rows(code, category),
                )
            typer.echo(format_range_json(result) if json_output else format_range_text(result))
            return

        query_date = _default_query_date(query_date)
        if category is None:
            result = _service().query_value(
                "index",
                code,
                "pb",
                query_date,
                lambda: fetch_index_pb_rows(code),
            )
        else:
            _validate_sw_category(category)
            result = _service().query_value(
                f"sw_index:{category}",
                code,
                "pb",
                query_date,
                lambda: fetch_sw_index_pb_rows(code, category, query_date=query_date),
            )
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(format_json(result) if json_output else format_text(result))


@app.command()
def gold(
    query_date: Annotated[str | None, typer.Option("--date")] = None,
    years: int | None = typer.Option(None, "--years"),
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query Au9999 gold close-price percentile."""
    try:
        if _is_range_mode(from_date, to_date):
            requested_from, requested_to = _validate_range_options(from_date, to_date, query_date, years)
            result = _service().query_range(
                "gold",
                "AU9999",
                "close",
                requested_from,
                requested_to,
                fetch_gold_rows,
            )
            typer.echo(format_range_json(result) if json_output else format_range_text(result))
            return

        query_date = _default_query_date(query_date)
        years = _default_years(years)
        validate_years(years)
        result = _service().query(
            "gold",
            "AU9999",
            "close",
            query_date,
            years,
            fetch_gold_rows,
        )
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(format_json(result) if json_output else format_text(result))


@app.command("cn10y-yield")
def cn10y_yield(
    query_date: Annotated[str | None, typer.Option("--date")] = None,
    years: int | None = typer.Option(None, "--years"),
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query China 10-year government bond yield percentile."""
    try:
        if _is_range_mode(from_date, to_date):
            requested_from, requested_to = _validate_range_options(from_date, to_date, query_date, years)
            result = _service().query_range(
                "bond",
                "CN10Y",
                "yield",
                requested_from,
                requested_to,
                fetch_cn10y_yield_rows,
            )
            typer.echo(format_range_json(result) if json_output else format_range_text(result))
            return

        query_date = _default_query_date(query_date)
        years = _default_years(years)
        validate_years(years)
        result = _service().query(
            "bond",
            "CN10Y",
            "yield",
            query_date,
            years,
            fetch_cn10y_yield_rows,
        )
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(format_json(result) if json_output else format_text(result))


@app.command("us10y-tips")
def us10y_tips(
    query_date: Annotated[str | None, typer.Option("--date")] = None,
    years: int | None = typer.Option(None, "--years"),
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query US 10-year TIPS real-yield percentile."""
    try:
        if _is_range_mode(from_date, to_date):
            requested_from, requested_to = _validate_range_options(from_date, to_date, query_date, years)
            from_year = parse_query_date(requested_from).year
            to_year = parse_query_date(requested_to).year
            fetch_years = range(from_year, to_year + 1)
            result = _service().query_range(
                "bond",
                "US10Y_TIPS",
                "yield",
                requested_from,
                requested_to,
                lambda: fetch_us10y_tips_yield_rows(years=fetch_years),
            )
            typer.echo(format_range_json(result) if json_output else format_range_text(result))
            return

        query_date = _default_query_date(query_date)
        years = _default_years(years)
        validate_years(years)
        parsed_query_date = parse_query_date(query_date)
        fetch_years = range(parsed_query_date.year - years, parsed_query_date.year + 1)
        result = _service().query(
            "bond",
            "US10Y_TIPS",
            "yield",
            query_date,
            years,
            lambda: fetch_us10y_tips_yield_rows(years=fetch_years),
        )
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(format_json(result) if json_output else format_text(result))


@app.command()
def m2(
    query_date: Annotated[str | None, typer.Option("--date")] = None,
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query US M2 money supply (no percentile)."""
    try:
        if _is_range_mode(from_date, to_date):
            requested_from, requested_to = _validate_range_options(from_date, to_date, query_date)
            result = _service().query_range(
                "macro",
                "M2SL",
                "money_supply",
                requested_from,
                requested_to,
                fetch_m2_rows,
            )
            typer.echo(format_range_json(result) if json_output else format_range_text(result))
            return

        query_date = _default_query_date(query_date)
        result = _service().query_value(
            "macro",
            "M2SL",
            "money_supply",
            query_date,
            fetch_m2_rows,
        )
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(format_json(result) if json_output else format_text(result))


@app.command("gold-usd")
def gold_usd(
    query_date: Annotated[str | None, typer.Option("--date")] = None,
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query gold price in USD per troy ounce (no percentile)."""
    try:
        if _is_range_mode(from_date, to_date):
            requested_from, requested_to = _validate_range_options(from_date, to_date, query_date)
            result = _service().query_range(
                "gold",
                "XAUUSD",
                "close",
                requested_from,
                requested_to,
                fetch_gold_usd_rows,
            )
            typer.echo(format_range_json(result) if json_output else format_range_text(result))
            return

        query_date = _default_query_date(query_date)
        result = _service().query_value(
            "gold",
            "XAUUSD",
            "close",
            query_date,
            fetch_gold_usd_rows,
        )
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(format_json(result) if json_output else format_text(result))


@app.command("gold-m2-ratio")
def gold_m2_ratio(
    query_date: Annotated[str | None, typer.Option("--date")] = None,
    years: int | None = typer.Option(None, "--years"),
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query gold(USD/oz) / M2(billion USD) ratio percentile."""
    try:
        if _is_range_mode(from_date, to_date):
            requested_from, requested_to = _validate_range_options(from_date, to_date, query_date, years)
            result = _service().query_range(
                "macro",
                "GOLD_M2",
                "ratio",
                requested_from,
                requested_to,
                fetch_gold_m2_ratio_rows,
            )
            typer.echo(format_range_json(result) if json_output else format_range_text(result))
            return

        query_date = _default_query_date(query_date)
        years = _default_years(years)
        validate_years(years)

        service = _service()

        def fetch_ratio():
            gold_rows = list(fetch_gold_usd_rows())
            m2_rows = list(fetch_m2_rows())
            service.repository.upsert_metrics(gold_rows)
            service.repository.upsert_metrics(m2_rows)
            return compute_gold_m2_ratio_rows(gold_rows, m2_rows)

        result = service.query(
            "macro",
            "GOLD_M2",
            "ratio",
            query_date,
            years,
            fetch_ratio,
        )
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(format_json(result) if json_output else format_text(result))


@app.command("dividend-yield-spread")
def dividend_yield_spread(
    query_date: Annotated[str | None, typer.Option("--date")] = None,
    code: str = typer.Option(..., "--code"),
    years: int | None = typer.Option(None, "--years"),
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query dividend yield spread (index dividend yield - CN10Y bond yield) percentile."""
    try:
        normalized_code = normalize_csindex_code(code)

        if _is_range_mode(from_date, to_date):
            requested_from, requested_to = _validate_range_options(from_date, to_date, query_date, years)
            result = _service().query_range(
                "spread",
                normalized_code,
                "dividend_yield_spread",
                requested_from,
                requested_to,
                lambda: fetch_dividend_yield_spread_rows(normalized_code),
            )
            typer.echo(format_range_json(result) if json_output else format_range_text(result))
            return

        query_date = _default_query_date(query_date)
        years = _default_years(years)
        validate_years(years)

        service = _service()

        def fetch_spread():
            # Sync latest dividend yield from API (incremental update)
            fresh_div = list(
                fetch_index_dividend_yield_rows(
                    normalized_code,
                    allow_history_failure=True,
                    history_failure_cutoff_date=query_date,
                )
            )
            service.repository.upsert_metrics(fresh_div)
            # Read full dividend yield history from DB (may span years from past syncs)
            div_rows = service.repository.metrics_between(
                "index", normalized_code, "dividend_yield", "1990-01-01", query_date
            )
            # Sync CN10Y yield
            cn10y_rows = list(fetch_cn10y_yield_rows())
            service.repository.upsert_metrics(cn10y_rows)
            return compute_dividend_yield_spread_rows(div_rows, cn10y_rows)

        result = service.query(
            "spread",
            normalized_code,
            "dividend_yield_spread",
            query_date,
            years,
            fetch_spread,
            ensure_lookback_coverage=True,
            minimum_lookback_years=3,
        )
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    if json_output:
        payload = json.loads(format_json(result))
        payload["dividend_yield"] = _lookup_value(
            service, "index", normalized_code, "dividend_yield", result.actual_date
        )
        payload["cn10y_yield"] = _lookup_value(
            service, "bond", "CN10Y", "yield", result.actual_date
        )
        typer.echo(json.dumps(payload, ensure_ascii=False))
    else:
        text = format_text(result)
        div_yield = _lookup_value(
            service, "index", normalized_code, "dividend_yield", result.actual_date
        )
        cn10y = _lookup_value(
            service, "bond", "CN10Y", "yield", result.actual_date
        )
        if div_yield is not None:
            text += f"\n股息率: {div_yield}"
        if cn10y is not None:
            text += f"\n10年期国债收益率: {cn10y}"
        typer.echo(text)


@app.command()
def erp(
    query_date: Annotated[str | None, typer.Option("--date")] = None,
    code: str = typer.Option(..., "--code"),
    years: int | None = typer.Option(None, "--years"),
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query equity risk premium (1 / PE_TTM * 100 - CN10Y yield) percentile."""
    try:
        normalized_code = normalize_index_pe_code(code)

        if _is_range_mode(from_date, to_date):
            requested_from, requested_to = _validate_range_options(from_date, to_date, query_date, years)
            result = _service().query_range(
                "spread",
                normalized_code,
                "erp",
                requested_from,
                requested_to,
                lambda: fetch_erp_rows(normalized_code),
            )
            typer.echo(format_range_json(result) if json_output else format_range_text(result))
            return

        query_date = _default_query_date(query_date)
        years = _default_years(years)
        validate_years(years)

        service = _service()

        def fetch_spread():
            pe_rows = list(fetch_index_pe_rows(normalized_code))
            service.repository.upsert_metrics(pe_rows)
            cn10y_rows = list(fetch_cn10y_yield_rows())
            service.repository.upsert_metrics(cn10y_rows)
            return compute_erp_rows(pe_rows, cn10y_rows)

        result = service.query(
            "spread",
            normalized_code,
            "erp",
            query_date,
            years,
            fetch_spread,
            ensure_lookback_coverage=True,
            minimum_lookback_years=3,
        )
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    pe_ttm = _lookup_value(service, "index", normalized_code, "rolling_pe", result.actual_date)
    cn10y = _lookup_value(service, "bond", "CN10Y", "yield", result.actual_date)
    earnings_yield = _earnings_yield(pe_ttm)
    if json_output:
        payload = json.loads(format_json(result))
        if pe_ttm is not None:
            payload["pe_ttm"] = pe_ttm
        if earnings_yield is not None:
            payload["earnings_yield"] = earnings_yield
        if cn10y is not None:
            payload["cn10y_yield"] = cn10y
        typer.echo(json.dumps(payload, ensure_ascii=False))
    else:
        text = format_text(result)
        if pe_ttm is not None:
            text += f"\nPE_TTM: {pe_ttm}"
        if earnings_yield is not None:
            text += f"\n盈利收益率: {earnings_yield}"
        if cn10y is not None:
            text += f"\n10年期国债收益率: {cn10y}"
        typer.echo(text)


@sync_app.command("pe")
def sync_pe(code: str = typer.Option(..., "--code")) -> None:
    """Synchronize index rolling PE history."""
    try:
        normalized_code = normalize_index_pe_code(code)
        inserted = _service().replace_sync(
            "index",
            normalized_code,
            "rolling_pe",
            lambda: fetch_index_pe_rows(normalized_code),
        )
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(f"同步 {inserted} 条记录")


@sync_app.command("dividend-yield")
def sync_dividend_yield(code: str = typer.Option(..., "--code")) -> None:
    """Synchronize index dividend-yield history."""
    try:
        normalized_code = normalize_csindex_code(code)
        inserted = _service().sync(lambda: fetch_index_dividend_yield_rows(normalized_code))
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(f"同步 {inserted} 条记录")


@sync_app.command("index")
def sync_index_value(code: str = typer.Option(..., "--code")) -> None:
    """Synchronize index value history."""
    try:
        normalized_code = normalize_index_value_code(code)
        inserted = _service().sync(lambda: fetch_index_value_rows(normalized_code))
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(f"同步 {inserted} 条记录")


@sync_app.command("pb")
def sync_pb(
    code: str = typer.Option(..., "--code"),
    category: str = typer.Option(..., "--category"),
) -> None:
    """Synchronize SW index PB history."""
    try:
        _validate_sw_category(category)
        inserted = _service().sync(lambda: fetch_sw_index_pb_rows(code, category))
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(f"同步 {inserted} 条记录")


@sync_app.command("gold")
def sync_gold() -> None:
    """Synchronize Au9999 gold price history."""
    try:
        inserted = _service().sync(fetch_gold_rows)
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(f"同步 {inserted} 条记录")


@sync_app.command("fund-info")
def sync_fund_info_command() -> None:
    """Synchronize all cached fund profile rows."""
    try:
        result = _service().sync_fund_info(lambda code: fetch_fund_info(code))
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    if result.total > 0 and result.updated == 0 and result.failed > 0:
        raise JsonClickException("runtime_error", "All fund info refreshes failed")

    typer.echo(
        f"同步基金基本信息：共 {result.total} 只，"
        f"成功 {result.updated} 只，失败 {result.failed} 只"
    )
    for success in result.successes:
        if success.changes:
            typer.secho(_format_fund_info_changes(success), fg="yellow", bold=True)
    for failure in result.failures:
        typer.echo(f"失败 {failure.code}: {failure.error}")


@sync_app.command("cn10y-yield")
def sync_cn10y_yield() -> None:
    """Synchronize China 10-year government bond yield history."""
    try:
        inserted = _service().sync(fetch_cn10y_yield_rows)
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(f"同步 {inserted} 条记录")


@sync_app.command("us10y-tips")
def sync_us10y_tips() -> None:
    """Synchronize US 10-year TIPS real-yield history."""
    try:
        inserted = _service().sync(fetch_us10y_tips_yield_rows)
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(f"同步 {inserted} 条记录")


@sync_app.command("m2")
def sync_m2() -> None:
    """Synchronize US M2 money supply history."""
    try:
        inserted = _service().sync(fetch_m2_rows)
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(f"同步 {inserted} 条记录")


@sync_app.command("gold-usd")
def sync_gold_usd() -> None:
    """Synchronize gold USD/oz price history."""
    try:
        inserted = _service().sync(fetch_gold_usd_rows)
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(f"同步 {inserted} 条记录")


@sync_app.command("gold-m2-ratio")
def sync_gold_m2_ratio() -> None:
    """Synchronize gold/M2 ratio history (also syncs gold USD and M2 data)."""
    try:
        service = _service()

        def fetch_all():
            gold_rows = list(fetch_gold_usd_rows())
            m2_rows = list(fetch_m2_rows())
            service.repository.upsert_metrics(gold_rows)
            service.repository.upsert_metrics(m2_rows)
            return compute_gold_m2_ratio_rows(gold_rows, m2_rows)

        inserted = service.sync(fetch_all)
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(f"同步 {inserted} 条记录")


@sync_app.command("dividend-yield-spread")
def sync_dividend_yield_spread(code: str = typer.Option(..., "--code")) -> None:
    """Synchronize dividend yield spread history (also syncs dividend yield and CN10Y data)."""
    try:
        normalized_code = normalize_csindex_code(code)
        service = _service()

        def fetch_all():
            # Sync latest dividend yield from API
            fresh_div = list(fetch_index_dividend_yield_rows(normalized_code))
            service.repository.upsert_metrics(fresh_div)
            # Read full dividend yield history from DB
            div_rows = service.repository.metrics_between(
                "index", normalized_code, "dividend_yield", "1990-01-01", "2099-12-31"
            )
            # Sync CN10Y yield
            cn10y_rows = list(fetch_cn10y_yield_rows())
            service.repository.upsert_metrics(cn10y_rows)
            return compute_dividend_yield_spread_rows(div_rows, cn10y_rows)

        inserted = service.sync(fetch_all)
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(f"同步 {inserted} 条记录")


@sync_app.command("erp")
def sync_erp(code: str = typer.Option(..., "--code")) -> None:
    """Synchronize ERP history (also syncs index PE and CN10Y data)."""
    try:
        normalized_code = normalize_index_pe_code(code)
        service = _service()

        def fetch_all():
            pe_rows = list(fetch_index_pe_rows(normalized_code))
            service.repository.upsert_metrics(pe_rows)
            cn10y_rows = list(fetch_cn10y_yield_rows())
            service.repository.upsert_metrics(cn10y_rows)
            return compute_erp_rows(pe_rows, cn10y_rows)

        inserted = service.sync(fetch_all)
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(f"同步 {inserted} 条记录")


def _format_fund_info_changes(success: object) -> str:
    changes = [
        f"{change.label} {_format_fund_info_change_value(change.field, change.old)} -> "
        f"{_format_fund_info_change_value(change.field, change.new)}"
        for change in success.changes
    ]
    return f"重要变更 {success.code} {success.name}: {'; '.join(changes)}"


def _format_fund_info_change_value(field: str, value: object) -> str:
    if value is None:
        return "无限制" if field == "purchase_limit_amount" else "未知"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{float(value):g}"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _lookup_value(
    service: MetricsService,
    asset_type: str,
    code: str,
    metric: str,
    query_date: str,
) -> float | None:
    """Look up a single metric value from the repository on a given date."""
    rows = service.repository.metrics_between(asset_type, code, metric, query_date, query_date)
    return rows[0].value if rows else None


def _earnings_yield(pe_ttm: float | None) -> float | None:
    if pe_ttm is None or pe_ttm <= 0:
        return None
    return 100 / pe_ttm


def _validate_sw_category(category: str) -> None:
    if category not in SW_INDEX_CATEGORIES:
        allowed = ", ".join(SW_INDEX_CATEGORIES)
        raise ValueError(f"category must be one of: {allowed}")
