import json

from .service import MetricQueryResult, MetricRangeQueryResult


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
        "money_supply": "M2货币供应量(十亿美元)",
        "ratio": "黄金/M2比值",
        "dividend_yield_spread": "股息率-国债收益率利差",
    }
    return labels.get(metric, metric)
