import json

from .service import MetricQueryResult


def format_json(result: MetricQueryResult) -> str:
    return json.dumps(
        {
            "asset_type": result.asset_type,
            "code": result.code,
            "metric": result.metric,
            "requested_date": result.requested_date,
            "actual_date": result.actual_date,
            "sample_start_date": result.sample_start_date,
            "value": result.value,
            "percentile": round(result.percentile, 1),
            "sample_count": result.sample_count,
            "source": result.source,
            "lookback_years": result.lookback_years,
        },
        ensure_ascii=False,
    )


def format_text(result: MetricQueryResult) -> str:
    label = _asset_label(result.asset_type)
    value_label = _metric_label(result.metric)
    return "\n".join(
        [
            f"{label}: {result.code}",
            f"请求日期: {result.requested_date}",
            f"实际数据日期: {result.actual_date}",
            f"指标: {result.metric}",
            f"数据源: {result.source}",
            f"回看年数: {result.lookback_years}",
            f"{value_label}: {result.value}",
            f"历史百分位: {round(result.percentile, 1)}%",
            f"样本数: {result.sample_count}",
            f"样本起始日期: {result.sample_start_date}",
        ]
    )


def _asset_label(asset_type: str) -> str:
    if asset_type == "gold":
        return "黄金"
    if asset_type == "bond":
        return "债券"
    return "指数"


def _metric_label(metric: str) -> str:
    labels = {
        "pe_ttm": "PE-TTM",
        "dividend_yield": "股息率",
        "pb": "PB",
        "yield": "收益率",
        "close": "收盘价",
    }
    return labels.get(metric, metric)
