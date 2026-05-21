import json

from .service import MetricQueryResult


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
    }
    return json.dumps(
        {key: value for key, value in payload.items() if value is not None},
        ensure_ascii=False,
    )


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
    if result.sample_count is not None:
        lines.append(f"样本数: {result.sample_count}")
    if result.sample_start_date is not None:
        lines.append(f"样本起始日期: {result.sample_start_date}")
    return "\n".join(lines)


def _asset_label(asset_type: str) -> str:
    if asset_type == "gold":
        return "黄金"
    if asset_type == "bond":
        return "债券"
    return "指数"


def _metric_label(metric: str) -> str:
    labels = {
        "rolling_pe": "滚动市盈率",
        "dividend_yield": "股息率",
        "pb": "PB",
        "yield": "收益率",
        "close": "收盘价",
    }
    return labels.get(metric, metric)
