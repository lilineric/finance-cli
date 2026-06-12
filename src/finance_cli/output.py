import json

from finance_cli.db import FundInfo

from .service import (
    MetricQueryResult,
    MetricRangeQueryResult,
    MoneyFundQueryResult,
    MoneyFundRangeQueryResult,
)


def format_json(result: MetricQueryResult) -> str:
    payload = {
        "asset_type": result.asset_type,
        "code": result.code,
        "metric": result.metric,
        "requested_date": result.requested_date,
        "actual_date": result.actual_date,
        "sample_start_date": result.sample_start_date,
        "value": result.value,
        "percentile": None if result.percentile is None else round(result.percentile, 1),
        "sample_count": result.sample_count,
        "source": result.source,
        "lookback_years": result.lookback_years,
        "coverage_status": result.coverage_status,
        "effective_years": result.effective_years,
    }
    if result.stale:
        payload["stale"] = True
    return json.dumps(
        {key: value for key, value in payload.items() if value is not None},
        ensure_ascii=False,
    )


def format_range_json(result: MetricRangeQueryResult) -> str:
    payload = {
        "asset_type": result.asset_type,
        "code": result.code,
        "metric": result.metric,
        "requested_from": result.requested_from,
        "requested_to": result.requested_to,
        "actual_start_date": result.actual_start_date,
        "actual_end_date": result.actual_end_date,
        "data": [
            {"date": row_date, "value": value, "source": source}
            for row_date, value, source in result.data
        ],
    }
    if result.stale:
        payload["stale"] = True
    return json.dumps(payload, ensure_ascii=False)


def format_money_fund_json(result: MoneyFundQueryResult) -> str:
    payload = {
        "asset_type": result.asset_type,
        "code": result.code,
        "fund_type": result.fund_type,
        "requested_date": result.requested_date,
        "actual_date": result.actual_date,
        "metrics": result.metrics,
        "source": result.source,
    }
    if result.stale:
        payload["stale"] = True
    return json.dumps(payload, ensure_ascii=False)


def format_money_fund_range_json(result: MoneyFundRangeQueryResult) -> str:
    payload = {
        "asset_type": result.asset_type,
        "code": result.code,
        "fund_type": result.fund_type,
        "requested_from": result.requested_from,
        "requested_to": result.requested_to,
        "actual_start_date": result.actual_start_date,
        "actual_end_date": result.actual_end_date,
        "data": [
            {"date": row_date, "metrics": metrics, "source": source}
            for row_date, metrics, source in result.data
        ],
    }
    if result.stale:
        payload["stale"] = True
    return json.dumps(payload, ensure_ascii=False)


def format_range_text(result: MetricRangeQueryResult) -> str:
    label = _asset_label(result.asset_type)
    lines = [
        f"{label}: {result.code}",
        f"请求起始日期: {result.requested_from}",
        f"请求结束日期: {result.requested_to}",
        f"实际起始日期: {result.actual_start_date}",
        f"实际结束日期: {result.actual_end_date}",
        f"指标: {result.metric}",
    ]
    lines.extend(
        f"{row_date} {value} {source}"
        for row_date, value, source in result.data
    )
    if result.stale:
        lines.append("⚠️ 数据源不可用，当前使用数据库中的存量数据，可能不是最新的。")
    return "\n".join(lines)


def format_money_fund_range_text(result: MoneyFundRangeQueryResult) -> str:
    lines = [
        f"基金: {result.code}",
        f"基金类型: {result.fund_type}",
        f"请求起始日期: {result.requested_from}",
        f"请求结束日期: {result.requested_to}",
        f"实际起始日期: {result.actual_start_date}",
        f"实际结束日期: {result.actual_end_date}",
    ]
    lines.extend(
        (
            f"{row_date} "
            f"每万份收益 {metrics['million_copies_income']} "
            f"7日年化收益率 {metrics['seven_day_annualized_yield']} "
            f"{source}"
        )
        for row_date, metrics, source in result.data
    )
    if result.stale:
        lines.append("⚠️ 数据源不可用，当前使用数据库中的存量数据，可能不是最新的。")
    return "\n".join(lines)


def format_fund_info_json(result: FundInfo) -> str:
    return json.dumps(
        {
            "code": result.code,
            "name": result.name,
            "fund_type": result.fund_type,
            "established_date": result.established_date,
            "asset_size": result.asset_size,
            "operation_fee": _operation_fee_json(result),
            "purchase_status": result.purchase_status,
            "purchase_limit_amount": result.purchase_limit_amount,
            "redemption_status": result.redemption_status,
            "morningstar_rating": result.morningstar_rating,
            "purchase_fee": result.purchase_fee,
            "redemption_fee": result.redemption_fee,
            "source": result.source,
            "updated_at": result.updated_at,
        },
        ensure_ascii=False,
    )


def format_fund_info_text(result: FundInfo) -> str:
    lines = [
        f"基金: {result.code}",
        f"基金名称: {result.name}",
        f"基金类型: {_display_value(result.fund_type)}",
        f"成立日期: {_display_value(result.established_date)}",
        f"资产规模: {_display_value(result.asset_size)}",
        f"运作费率: {_format_annual_rate(result.operation_fee.total)}",
        f"  管理费率: {_format_annual_rate(result.operation_fee.management_fee)}",
        f"  托管费率: {_format_annual_rate(result.operation_fee.custodian_fee)}",
        f"  销售服务费率: {_format_annual_rate(result.operation_fee.sales_service_fee)}",
        f"申购状态: {_purchase_status_text(result)}",
    ]
    lines.extend(
        [
            f"赎回状态: {_display_value(result.redemption_status)}",
            f"晨星评级: {_display_value(result.morningstar_rating)}",
            f"数据源: {result.source}",
            f"更新时间: {result.updated_at}",
            "申购费率:",
        ]
    )
    lines.extend(_purchase_fee_lines(result.purchase_fee))
    lines.append("赎回费率:")
    lines.extend(_redemption_fee_lines(result.redemption_fee))
    return "\n".join(lines)


def format_text(result: MetricQueryResult) -> str:
    label = _asset_label(result.asset_type)
    value_label = _metric_label(result.metric)
    lines = [
        f"{label}: {result.code}",
        f"请求日期: {result.requested_date}",
        f"实际数据日期: {result.actual_date}",
        f"指标: {result.metric}",
        f"数据源: {result.source}",
    ]
    if result.lookback_years is not None:
        lines.append(f"回看年数: {result.lookback_years}")
    lines.append(f"{value_label}: {result.value}")
    if result.percentile is not None:
        lines.append(f"历史百分位: {round(result.percentile, 1)}%")
    if result.coverage_status == "partial" and result.effective_years is not None:
        lines.append(f"样本覆盖: 不足{result.lookback_years}年，使用全部可用数据，约{result.effective_years}年")
    if result.sample_count is not None:
        lines.append(f"样本数: {result.sample_count}")
    if result.sample_start_date is not None:
        lines.append(f"样本起始日期: {result.sample_start_date}")
    if result.stale:
        lines.append("⚠️ 数据源不可用，当前使用数据库中的存量数据，可能不是最新的。")
    return "\n".join(lines)


def format_money_fund_text(result: MoneyFundQueryResult) -> str:
    lines = [
        f"基金: {result.code}",
        f"基金类型: {result.fund_type}",
        f"请求日期: {result.requested_date}",
        f"实际数据日期: {result.actual_date}",
        f"数据源: {result.source}",
        f"每万份收益: {result.metrics['million_copies_income']}",
        f"7日年化收益率: {result.metrics['seven_day_annualized_yield']}",
    ]
    if result.stale:
        lines.append("⚠️ 数据源不可用，当前使用数据库中的存量数据，可能不是最新的。")
    return "\n".join(lines)


def _display_value(value: object) -> str:
    return "未知" if value is None else str(value)


def _operation_fee_json(result: FundInfo) -> dict[str, float | None]:
    return {
        "total": _json_rate(result.operation_fee.total),
        "management_fee": _json_rate(result.operation_fee.management_fee),
        "custodian_fee": _json_rate(result.operation_fee.custodian_fee),
        "sales_service_fee": _json_rate(result.operation_fee.sales_service_fee),
    }


def _json_rate(value: float | None) -> float | None:
    return None if value is None else round(float(value), 12)


def _purchase_fee_lines(fee_tiers: list[dict[str, object]]) -> list[str]:
    if not fee_tiers:
        return ["无"]
    return [_format_purchase_fee_tier(tier) for tier in fee_tiers]


def _redemption_fee_lines(fee_tiers: list[dict[str, object]]) -> list[str]:
    if not fee_tiers:
        return ["无"]
    return [_format_redemption_fee_tier(tier) for tier in fee_tiers]


def _purchase_status_text(result: FundInfo) -> str:
    status = _display_value(result.purchase_status)
    if result.purchase_limit_amount is not None and result.purchase_limit_amount > 0:
        return f"{status}（日累计限定金额 {_format_amount(result.purchase_limit_amount)}元）"
    return status


def _format_purchase_fee_tier(tier: dict[str, object]) -> str:
    min_amount = tier["min_amount"]
    max_amount = tier.get("max_amount")
    if max_amount is None:
        range_text = f"amount >= {min_amount}"
    else:
        range_text = f"{min_amount} <= amount < {max_amount}"
    return f"{range_text}: {_format_fee_value(tier)}"


def _format_redemption_fee_tier(tier: dict[str, object]) -> str:
    min_days = tier["min_holding_days"]
    max_days = tier.get("max_holding_days")
    if max_days is None:
        range_text = f"days >= {min_days}"
    else:
        range_text = f"{min_days} <= days < {max_days}"
    return f"{range_text}: {_format_fee_value(tier)}"


def _format_fee_value(tier: dict[str, object]) -> str:
    fixed_fee = tier.get("fixed_fee")
    if fixed_fee is not None:
        return f"固定费用 {fixed_fee}元"
    return (
        f"原费率 {_format_rate(tier.get('original_rate'))}, "
        f"折扣后费率 {_format_rate(tier.get('discounted_rate'))}"
    )


def _format_rate(value: object) -> str:
    if value is None:
        return "未知"
    percentage = float(value) * 100
    return f"{percentage:g}%"


def _format_annual_rate(value: float | None) -> str:
    if value is None:
        return "未知"
    return f"{float(value) * 100:.2f}%（每年）"


def _format_amount(value: object) -> str:
    return f"{float(value):g}"


def _asset_label(asset_type: str) -> str:
    if asset_type == "gold":
        return "黄金"
    if asset_type == "bond":
        return "债券"
    if asset_type == "fund":
        return "基金"
    if asset_type == "macro":
        return "宏观"
    if asset_type == "spread":
        return "利差"
    return "指数"


def _metric_label(metric: str) -> str:
    labels = {
        "rolling_pe": "滚动市盈率",
        "dividend_yield": "股息率",
        "pb": "PB",
        "yield": "收益率",
        "close": "收盘价",
        "unit_nav": "单位净值",
        "accumulated_nav": "累计净值",
        "million_copies_income": "每万份收益",
        "seven_day_annualized_yield": "7日年化收益率",
        "money_supply": "M2货币供应量(十亿美元)",
        "ratio": "黄金/M2比值",
        "dividend_yield_spread": "股息率-国债收益率利差",
        "erp": "股债利差（ERP）",
    }
    return labels.get(metric, metric)
