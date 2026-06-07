import json

from finance_cli.db import FundInfo
from finance_cli.output import (
    format_fund_info_json,
    format_fund_info_text,
    format_json,
    format_range_json,
    format_range_text,
    format_text,
)
from finance_cli.service import MetricQueryResult, MetricRangeQueryResult


def test_format_json_uses_stable_keys():
    result = MetricQueryResult("index", "000300", "rolling_pe", "2026-04-20", "2026-04-17", "2020-01-02", 12.34, 42.8, 2000, "akshare", 10)

    payload = json.loads(format_json(result))

    assert set(payload) == {
        "asset_type",
        "code",
        "metric",
        "requested_date",
        "actual_date",
        "sample_start_date",
        "value",
        "percentile",
        "sample_count",
        "source",
        "lookback_years",
    }
    assert payload["asset_type"] == "index"
    assert payload["code"] == "000300"
    assert payload["metric"] == "rolling_pe"
    assert payload["requested_date"] == "2026-04-20"
    assert payload["actual_date"] == "2026-04-17"
    assert payload["sample_start_date"] == "2020-01-02"
    assert payload["value"] == 12.34
    assert payload["percentile"] == 42.8
    assert payload["sample_count"] == 2000
    assert payload["source"] == "akshare"
    assert payload["lookback_years"] == 10


def test_format_text_includes_index_pe_labels_and_key_fields():
    result = MetricQueryResult("index", "000300", "rolling_pe", "2026-04-20", "2026-04-17", "2020-01-02", 12.34, 42.8, 2000, "akshare", 10)

    text = format_text(result)

    assert "指数: 000300" in text
    assert "请求日期: 2026-04-20" in text
    assert "实际数据日期: 2026-04-17" in text
    assert "滚动市盈率: 12.34" in text
    assert "历史百分位: 42.8%" in text
    assert "样本数: 2000" in text
    assert "样本起始日期: 2020-01-02" in text
    assert "回看年数: 10" in text


def test_format_output_marks_partial_coverage():
    result = MetricQueryResult(
        "index",
        "990001",
        "rolling_pe",
        "2026-05-23",
        "2026-05-22",
        "2020-02-27",
        114.73,
        80.0,
        1511,
        "akshare",
        10,
        "partial",
        6.2,
    )

    payload = json.loads(format_json(result))
    text = format_text(result)

    assert payload["coverage_status"] == "partial"
    assert payload["effective_years"] == 6.2
    assert "样本覆盖: 不足10年，使用全部可用数据，约6.2年" in text


def test_format_text_includes_gold_close_labels_and_key_fields():
    result = MetricQueryResult("gold", "AU9999", "close", "2026-04-20", "2026-04-17", "2021-03-01", 535.2, 80.0, 2400, "akshare", 5)

    text = format_text(result)

    assert "黄金: AU9999" in text
    assert "请求日期: 2026-04-20" in text
    assert "实际数据日期: 2026-04-17" in text
    assert "收盘价: 535.2" in text
    assert "历史百分位: 80.0%" in text
    assert "样本数: 2400" in text
    assert "样本起始日期: 2021-03-01" in text
    assert "回看年数: 5" in text


def test_format_text_includes_fund_nav_labels():
    unit = MetricQueryResult("fund", "017763", "unit_nav", "2026-05-23", "2026-05-22", None, 1.2456, None, None, "akshare", None)
    accumulated = MetricQueryResult(
        "fund",
        "017763",
        "accumulated_nav",
        "2026-05-23",
        "2026-05-22",
        None,
        1.9876,
        None,
        None,
        "akshare",
        None,
    )

    assert "基金: 017763" in format_text(unit)
    assert "单位净值: 1.2456" in format_text(unit)
    assert "累计净值: 1.9876" in format_text(accumulated)


def test_format_fund_info_json_outputs_expected_payload():
    fund_info = FundInfo(
        code="017763",
        name="银河领先债券C",
        fund_type="债券型",
        established_date="2023-01-01",
        asset_size="10.25亿元",
        purchase_status="开放申购",
        redemption_status="开放赎回",
        morningstar_rating="5",
        purchase_fee=[
            {
                "min_amount": 0,
                "max_amount": 1000000,
                "original_rate": 0.015,
                "discounted_rate": 0.0015,
            }
        ],
        redemption_fee=[
            {
                "min_holding_days": 0,
                "max_holding_days": None,
                "original_rate": 0,
                "discounted_rate": 0,
            }
        ],
        source="akshare",
        updated_at="2026-06-07T12:00:00+00:00",
        purchase_limit_amount=1000.0,
    )

    payload = json.loads(format_fund_info_json(fund_info))

    assert payload["code"] == "017763"
    assert payload["name"] == "银河领先债券C"
    assert payload["purchase_fee"][0]["discounted_rate"] == 0.0015
    assert payload["redemption_fee"][0]["max_holding_days"] is None
    assert payload["purchase_limit_amount"] == 1000.0
    assert payload["source"] == "akshare"


def test_format_fund_info_text_outputs_chinese_labels_and_fee_tiers():
    fund_info = FundInfo(
        code="017763",
        name="银河领先债券C",
        fund_type="债券型",
        established_date="2023-01-01",
        asset_size="10.25亿元",
        purchase_status="开放申购",
        redemption_status="开放赎回",
        morningstar_rating="5",
        purchase_fee=[
            {
                "min_amount": 0,
                "max_amount": 1000000,
                "original_rate": 0.015,
                "discounted_rate": 0.0015,
            },
            {
                "min_amount": 1000000,
                "max_amount": None,
                "original_rate": None,
                "discounted_rate": None,
                "fixed_fee": 1000,
            },
        ],
        redemption_fee=[
            {
                "min_holding_days": 0,
                "max_holding_days": 7,
                "original_rate": 0.015,
                "discounted_rate": 0.015,
            }
        ],
        source="manual",
        updated_at="2026-06-07T12:00:00+00:00",
    )

    text = format_fund_info_text(fund_info)

    assert "基金: 017763" in text
    assert "基金名称: 银河领先债券C" in text
    assert "晨星评级: 5" in text
    assert "申购费率:" in text
    assert "0 <= amount < 1000000: 原费率 1.5%, 折扣后费率 0.15%" in text
    assert "amount >= 1000000: 固定费用 1000元" in text
    assert "赎回费率:" in text
    assert "0 <= days < 7: 原费率 1.5%, 折扣后费率 1.5%" in text


def test_format_fund_info_text_outputs_purchase_limit_detail():
    fund_info = FundInfo(
        code="017436",
        name="华宝纳斯达克精选股票发起式(QDII)A",
        fund_type="QDII-股票",
        established_date="2023-03-02",
        asset_size="39.51亿",
        purchase_status="限大额",
        redemption_status="开放赎回",
        morningstar_rating="4.0",
        purchase_fee=[],
        redemption_fee=[],
        source="akshare",
        updated_at="2026-06-07T03:13:07.136543+00:00",
        purchase_limit_amount=1000.0,
    )

    text = format_fund_info_text(fund_info)

    assert "申购状态: 限大额（日累计限定金额 1000元）" in text
    assert "申购限额:" not in text


def test_format_fund_info_text_omits_purchase_limit_when_unlimited():
    fund_info = FundInfo(
        code="017763",
        name="银河领先债券C",
        fund_type="债券型",
        established_date="2023-01-01",
        asset_size="10.25亿元",
        purchase_status="开放申购",
        redemption_status="开放赎回",
        morningstar_rating="5",
        purchase_fee=[],
        redemption_fee=[],
        source="akshare",
        updated_at="2026-06-07T12:00:00+00:00",
        purchase_limit_amount=None,
    )

    text = format_fund_info_text(fund_info)

    assert "申购状态: 开放申购" in text
    assert "日累计限定金额" not in text


def test_format_fund_info_json_outputs_null_purchase_limit_when_unlimited():
    fund_info = FundInfo(
        code="017763",
        name="银河领先债券C",
        fund_type="债券型",
        established_date="2023-01-01",
        asset_size="10.25亿元",
        purchase_status="开放申购",
        redemption_status="开放赎回",
        morningstar_rating="5",
        purchase_fee=[],
        redemption_fee=[],
        source="akshare",
        updated_at="2026-06-07T12:00:00+00:00",
        purchase_limit_amount=None,
    )

    payload = json.loads(format_fund_info_json(fund_info))

    assert payload["purchase_limit_amount"] is None


def test_format_fund_info_text_omits_purchase_limit_when_buying_unavailable():
    fund_info = FundInfo(
        code="000032",
        name="易方达信用债债券A",
        fund_type="债券型",
        established_date="2013-04-24",
        asset_size="10.25亿元",
        purchase_status="暂停申购",
        redemption_status="开放赎回",
        morningstar_rating=None,
        purchase_fee=[],
        redemption_fee=[],
        source="akshare",
        updated_at="2026-06-07T12:00:00+00:00",
        purchase_limit_amount=0,
    )

    text = format_fund_info_text(fund_info)

    assert "申购状态: 暂停申购" in text
    assert "日累计限定金额" not in text


def test_format_output_omits_percentile_when_unavailable():
    result = MetricQueryResult(
        "index",
        "000300",
        "dividend_yield",
        "2026-05-22",
        "2026-05-21",
        None,
        2.32,
        None,
        None,
        "akshare",
        None,
    )

    payload = json.loads(format_json(result))
    text = format_text(result)

    assert "percentile" not in payload
    assert "lookback_years" not in payload
    assert "sample_count" not in payload
    assert "sample_start_date" not in payload
    assert "股息率: 2.32" in text
    assert "历史百分位" not in text
    assert "回看年数" not in text
    assert "样本数" not in text
    assert "样本起始日期" not in text


def test_format_text_includes_new_metric_labels():
    dividend = MetricQueryResult("index", "000300", "dividend_yield", "2026-04-20", "2026-04-17", "2020-01-02", 3.1, 70.0, 2000, "akshare", 10)
    pb = MetricQueryResult("sw_index:一级行业", "801010", "pb", "2026-04-20", "2026-04-17", "2020-01-02", 1.8, 35.0, 2000, "akshare", 10)
    cn10y = MetricQueryResult("bond", "CN10Y", "yield", "2026-04-20", "2026-04-17", "2020-01-02", 1.7, 20.0, 2000, "akshare", 10)

    assert "股息率: 3.1" in format_text(dividend)
    assert "PB: 1.8" in format_text(pb)
    assert "收益率: 1.7" in format_text(cn10y)


def test_format_range_json_uses_stable_keys_and_raw_values_only():
    result = MetricRangeQueryResult(
        "index",
        "000300",
        "rolling_pe",
        "2026-01-01",
        "2026-05-01",
        "2026-01-02",
        "2026-04-30",
        [
            ("2026-01-02", 12.3, "akshare"),
            ("2026-04-30", 12.8, "akshare"),
        ],
    )

    payload = json.loads(format_range_json(result))

    assert set(payload) == {
        "asset_type",
        "code",
        "metric",
        "requested_from",
        "requested_to",
        "actual_start_date",
        "actual_end_date",
        "data",
    }
    assert payload["actual_start_date"] == "2026-01-02"
    assert payload["actual_end_date"] == "2026-04-30"
    assert payload["data"] == [
        {"date": "2026-01-02", "value": 12.3, "source": "akshare"},
        {"date": "2026-04-30", "value": 12.8, "source": "akshare"},
    ]
    assert "percentile" not in json.dumps(payload)
    assert "sample_count" not in json.dumps(payload)
    assert "lookback_years" not in json.dumps(payload)


def test_format_range_text_omits_percentile_fields():
    result = MetricRangeQueryResult(
        "gold",
        "AU9999",
        "close",
        "2026-01-01",
        "2026-05-01",
        "2026-01-02",
        "2026-04-30",
        [
            ("2026-01-02", 530.0, "akshare"),
            ("2026-04-30", 540.0, "akshare"),
        ],
    )

    text = format_range_text(result)

    assert "黄金: AU9999" in text
    assert "请求起始日期: 2026-01-01" in text
    assert "请求结束日期: 2026-05-01" in text
    assert "实际起始日期: 2026-01-02" in text
    assert "实际结束日期: 2026-04-30" in text
    assert "2026-01-02 530.0 akshare" in text
    assert "2026-04-30 540.0 akshare" in text
    assert "历史百分位" not in text
    assert "回看年数" not in text
    assert "样本数" not in text
    assert "样本起始日期" not in text


def test_format_text_includes_macro_labels():
    m2_result = MetricQueryResult(
        "macro", "M2SL", "money_supply", "2026-05-22", "2026-05-01",
        None, 21500.5, None, None, "fred", None,
    )
    ratio_result = MetricQueryResult(
        "macro", "GOLD_M2", "ratio", "2026-05-22", "2026-05-20",
        "2020-01-02", 118.5, 45.0, 1500, "fred", 5,
    )

    m2_text = format_text(m2_result)
    ratio_text = format_text(ratio_result)

    assert "宏观: M2SL" in m2_text
    assert "M2货币供应量(十亿美元): 21500.5" in m2_text
    assert "宏观: GOLD_M2" in ratio_text
    assert "黄金/M2比值: 118.5" in ratio_text
    assert "历史百分位: 45.0%" in ratio_text


def test_format_output_omits_percentile_for_m2_value_only():
    result = MetricQueryResult(
        "macro", "M2SL", "money_supply", "2026-05-22", "2026-05-01",
        None, 21500.5, None, None, "fred", None,
    )

    payload = json.loads(format_json(result))

    assert "percentile" not in payload
    assert "lookback_years" not in payload
    assert "sample_count" not in payload
    assert "sample_start_date" not in payload


def test_format_text_includes_spread_labels():
    result = MetricQueryResult(
        "spread", "H30269", "dividend_yield_spread", "2026-05-30", "2026-05-29",
        "2020-01-02", 2.88, 35.0, 1500, "akshare", 5,
    )

    text = format_text(result)

    assert "利差: H30269" in text
    assert "股息率-国债收益率利差: 2.88" in text
    assert "历史百分位: 35.0%" in text
    assert "样本数: 1500" in text
