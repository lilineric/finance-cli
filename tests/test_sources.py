import json
from datetime import date

import pandas as pd
import pytest

from finance_cli.sources import (
    DataSourceError,
    compute_dividend_yield_spread_rows,
    compute_erp_rows,
    compute_gold_m2_ratio_rows,
    fetch_cn10y_yield_rows,
    fetch_dividend_yield_spread_rows,
    fetch_erp_rows,
    fetch_gold_rows,
    fetch_gold_m2_ratio_rows,
    fetch_gold_usd_rows,
    fetch_index_dividend_yield_rows,
    fetch_index_dividend_yield_history_rows,
    fetch_index_value_rows,
    fetch_index_pb_rows,
    fetch_index_pe_rows,
    fetch_fund_info,
    fetch_fund_is_money_fund,
    fetch_money_fund_rows,
    fetch_fund_nav_rows,
    fetch_m2_rows,
    fetch_us10y_tips_yield_rows,
    normalize_index_pe_code,
    normalize_ndx_pe_rows,
    fetch_sw_index_pb_rows,
    normalize_danjuan_index_pe_rows,
    normalize_csindex_code,
    normalize_fund_info,
    normalize_money_fund_rows,
    normalize_fund_nav_rows,
    normalize_purchase_fee_rows,
    normalize_index_pb_rows_from_etf_run,
    normalize_redemption_fee_rows,
    normalize_cn10y_yield_rows,
    normalize_gold_rows,
    normalize_index_dividend_yield_rows,
    normalize_index_value_rows,
    normalize_funddb_index_dividend_yield_rows,
    merge_index_dividend_yield_rows,
    normalize_index_pe_rows,
    normalize_worldperatio_pe_rows,
    normalize_sw_index_pb_rows,
    _fetch_text,
    _fund_basic_frame_from_eastmoney_html,
    _operation_fee_from_eastmoney_html,
    _to_danjuan_index_code,
)
from finance_cli.db import DailyMetric, OperationFee
from io import BytesIO
from urllib.error import HTTPError


def test_normalize_index_pe_rows_accepts_common_akshare_columns():
    frame = pd.DataFrame(
        {
            "日期": ["2026-04-17", "2026-04-20"],
            "滚动市盈率": [12.3, 12.8],
        }
    )

    rows = normalize_index_pe_rows("000300", frame)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("index", "000300", "rolling_pe", "2026-04-17", 12.3, "akshare"),
        ("index", "000300", "rolling_pe", "2026-04-20", 12.8, "akshare"),
    ]


def test_normalize_index_pe_rows_accepts_csindex_indicator_columns():
    frame = pd.DataFrame(
        {
            "日期Date": [20260522, 20260521],
            "市盈率1（总股本）P/E1": [119.66, 117.03],
            "市盈率2（计算用股本）P/E2": [114.73, 111.75],
        }
    )

    rows = normalize_index_pe_rows("990001", frame)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("index", "990001", "rolling_pe", "2026-05-22", 114.73, "akshare"),
        ("index", "990001", "rolling_pe", "2026-05-21", 111.75, "akshare"),
    ]


def test_normalize_index_pe_rows_prefers_rolling_pe():
    frame = pd.DataFrame(
        {
            "日期": ["2026-04-17"],
            "市盈率2": [12.3],
            "滚动市盈率": [14.2],
        }
    )

    rows = normalize_index_pe_rows("000300", frame)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("index", "000300", "rolling_pe", "2026-04-17", 14.2, "akshare"),
    ]


def test_normalize_index_pe_rows_skips_missing_pe_values():
    frame = pd.DataFrame(
        {
            "日期": ["2013-12-04", "2013-12-05"],
            "滚动市盈率": [float("nan"), 7.36],
        }
    )

    rows = normalize_index_pe_rows("H30269", frame)

    assert [(row.code, row.date, row.value) for row in rows] == [("H30269", "2013-12-05", 7.36)]


def test_normalize_gold_rows_accepts_common_akshare_columns():
    frame = pd.DataFrame(
        {
            "日期": ["2026-04-17", "2026-04-20"],
            "收盘价": [530.5, 535.2],
        }
    )

    rows = normalize_gold_rows(frame)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("gold", "AU9999", "close", "2026-04-17", 530.5, "akshare"),
        ("gold", "AU9999", "close", "2026-04-20", 535.2, "akshare"),
    ]


def test_normalize_index_value_rows_accepts_trendforce_imci_json():
    payload = {
        "上期所有色金屬價格指數(IMCI)": {
            "data": {
                "2026-06-10T16:00:00.000Z": "5351.37",
                "2026-06-11T16:00:00.000Z": "5410.94",
            },
            "data_source": "Shanghai Futures Exchange (Choice)",
        }
    }

    rows = normalize_index_value_rows("IMCI", json.dumps(payload))

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("index", "IMCI", "price_index", "2026-06-11", 5351.37, "trendforce"),
        ("index", "IMCI", "price_index", "2026-06-12", 5410.94, "trendforce"),
    ]


def test_normalize_index_value_rows_rejects_missing_trendforce_data():
    payload = {"上期所有色金屬價格指數(IMCI)": {"data": {}}}

    with pytest.raises(DataSourceError, match="No index value data found for IMCI"):
        normalize_index_value_rows("IMCI", json.dumps(payload))


def test_normalize_fund_nav_rows_accepts_unit_nav_columns():
    frame = pd.DataFrame(
        {
            "净值日期": ["2026-05-21", "2026-05-22"],
            "单位净值": [1.2345, 1.2456],
        }
    )

    rows = normalize_fund_nav_rows("017763", "unit_nav", frame)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("fund", "017763", "unit_nav", "2026-05-21", 1.2345, "akshare"),
        ("fund", "017763", "unit_nav", "2026-05-22", 1.2456, "akshare"),
    ]


def test_normalize_fund_nav_rows_accepts_accumulated_nav_columns():
    frame = pd.DataFrame(
        {
            "净值日期": ["2026-05-22"],
            "累计净值": [1.9876],
        }
    )

    rows = normalize_fund_nav_rows("017763", "accumulated_nav", frame)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("fund", "017763", "accumulated_nav", "2026-05-22", 1.9876, "akshare"),
    ]


def test_normalize_money_fund_rows_outputs_income_and_yield_metrics():
    frame = pd.DataFrame(
        {
            "净值日期": ["2026-06-06", "2026-06-07"],
            "每万份收益": [0.3571, 0.3572],
            "7日年化收益率": [1.343, 1.342],
        }
    )

    rows = normalize_money_fund_rows("001821", frame)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("fund", "001821", "million_copies_income", "2026-06-06", 0.3571, "akshare"),
        ("fund", "001821", "seven_day_annualized_yield", "2026-06-06", 1.343, "akshare"),
        ("fund", "001821", "million_copies_income", "2026-06-07", 0.3572, "akshare"),
        ("fund", "001821", "seven_day_annualized_yield", "2026-06-07", 1.342, "akshare"),
    ]


def test_normalize_purchase_fee_rows_parses_amount_tiers_and_discount_rates():
    frame = pd.DataFrame(
        {
            "适用金额": ["小于100万元", "大于等于100万元"],
            "原费率": ["1.50%", "1000元/笔"],
            "天天基金优惠费率": ["0.15%", "1000元/笔"],
        }
    )

    tiers = normalize_purchase_fee_rows(frame)

    assert tiers == [
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
    ]


def test_normalize_purchase_fee_rows_parses_eastmoney_combined_rate_column():
    frame = pd.DataFrame(
        {
            "适用金额": ["小于100万元", "大于等于100万元，小于200万元", "大于等于200万元"],
            "原费率|天天基金优惠费率": ["1.50% | 0.15%", "1.00% | 0.10%", "每笔1000元"],
        }
    )

    tiers = normalize_purchase_fee_rows(frame)

    assert tiers == [
        {
            "min_amount": 0,
            "max_amount": 1000000,
            "original_rate": 0.015,
            "discounted_rate": 0.0015,
        },
        {
            "min_amount": 1000000,
            "max_amount": 2000000,
            "original_rate": 0.01,
            "discounted_rate": 0.001,
        },
        {
            "min_amount": 2000000,
            "max_amount": None,
            "original_rate": None,
            "discounted_rate": None,
            "fixed_fee": 1000,
        },
    ]


def test_normalize_purchase_fee_rows_parses_flat_zero_fee_row():
    frame = pd.DataFrame(
        {
            "适用金额": ["---"],
            "费率": ["0.00%"],
        }
    )

    tiers = normalize_purchase_fee_rows(frame)

    assert tiers == [
        {
            "min_amount": 0,
            "max_amount": None,
            "original_rate": 0,
            "discounted_rate": 0,
        }
    ]


def test_normalize_redemption_fee_rows_parses_holding_period_tiers():
    frame = pd.DataFrame(
        {
            "持有期限": ["小于7天", "大于等于730天"],
            "赎回费率": ["1.50%", "0.00%"],
        }
    )

    tiers = normalize_redemption_fee_rows(frame)

    assert tiers == [
        {
            "min_holding_days": 0,
            "max_holding_days": 7,
            "original_rate": 0.015,
            "discounted_rate": 0.015,
        },
        {
            "min_holding_days": 730,
            "max_holding_days": None,
            "original_rate": 0,
            "discounted_rate": 0,
        },
    ]


def test_normalize_redemption_fee_rows_parses_flat_zero_fee_row():
    frame = pd.DataFrame(
        {
            "适用期限": ["---"],
            "赎回费率": ["0.00%"],
        }
    )

    tiers = normalize_redemption_fee_rows(frame)

    assert tiers == [
        {
            "min_holding_days": 0,
            "max_holding_days": None,
            "original_rate": 0,
            "discounted_rate": 0,
        }
    ]


def test_normalize_redemption_fee_rows_parses_usual_no_fee_text():
    frame = pd.DataFrame(
        {
            "适用期限": ["在通常情况下不收取赎回费用"],
            "赎回费率": ["0.00%"],
        }
    )

    tiers = normalize_redemption_fee_rows(frame)

    assert tiers == [
        {
            "min_holding_days": 0,
            "max_holding_days": None,
            "original_rate": 0,
            "discounted_rate": 0,
        }
    ]


def test_normalize_redemption_fee_rows_parses_general_no_fee_text():
    frame = pd.DataFrame(
        {
            "适用期限": ["一般情况下,不收取赎回费"],
            "赎回费率": ["0.00%"],
        }
    )

    tiers = normalize_redemption_fee_rows(frame)

    assert tiers == [
        {
            "min_holding_days": 0,
            "max_holding_days": None,
            "original_rate": 0,
            "discounted_rate": 0,
        }
    ]


def test_normalize_redemption_fee_rows_parses_normal_no_fee_text():
    frame = pd.DataFrame(
        {
            "适用期限": ["正常情况下,不收取赎回费"],
            "赎回费率": ["0.00%"],
        }
    )

    tiers = normalize_redemption_fee_rows(frame)

    assert tiers == [
        {
            "min_holding_days": 0,
            "max_holding_days": None,
            "original_rate": 0,
            "discounted_rate": 0,
        }
    ]


def test_normalize_redemption_fee_rows_parses_no_purchase_or_redemption_fee_text():
    frame = pd.DataFrame(
        {
            "适用期限": ["本基金通常不收取申购费用和赎回费用"],
            "赎回费率": ["0.00%"],
        }
    )

    tiers = normalize_redemption_fee_rows(frame)

    assert tiers == [
        {
            "min_holding_days": 0,
            "max_holding_days": None,
            "original_rate": 0,
            "discounted_rate": 0,
        }
    ]


def test_normalize_redemption_fee_rows_skips_conditional_forced_fee_text():
    frame = pd.DataFrame(
        {
            "适用期限": [
                "在通常情况下不收取赎回费用",
                "在满足相关流动性风险管理要求的前提下,当本基金持有的现金、国债、中央银行票据、"
                "政策性金融债券以及5个交易日内到期的其他金融工具占基金资产净值的比例合计低于5%"
                "且偏离度为负时,为确保基金平稳运作,避免诱发系统性风险,基金管理人应当对当日单个"
                "基金份额持有人申请赎回基金份额超过基金总份额1%以上的赎回申请征收1%的强制赎回费用,"
                "并将上述赎回费用全额计入基金财产。",
            ],
            "赎回费率": ["0.00%", "1.00%"],
        }
    )

    tiers = normalize_redemption_fee_rows(frame)

    assert tiers == [
        {
            "min_holding_days": 0,
            "max_holding_days": None,
            "original_rate": 0,
            "discounted_rate": 0,
        }
    ]


def test_normalize_redemption_fee_rows_accepts_applicable_period_column_and_comma_ranges():
    frame = pd.DataFrame(
        {
            "适用期限": ["小于7天", "大于等于7天，小于30天", "大于等于30天，小于180天", "大于等于180天"],
            "赎回费率": ["1.50%", "0.50%", "0.10%", "0.00%"],
        }
    )

    tiers = normalize_redemption_fee_rows(frame)

    assert tiers == [
        {
            "min_holding_days": 0,
            "max_holding_days": 7,
            "original_rate": 0.015,
            "discounted_rate": 0.015,
        },
        {
            "min_holding_days": 7,
            "max_holding_days": 30,
            "original_rate": 0.005,
            "discounted_rate": 0.005,
        },
        {
            "min_holding_days": 30,
            "max_holding_days": 180,
            "original_rate": 0.001,
            "discounted_rate": 0.001,
        },
        {
            "min_holding_days": 180,
            "max_holding_days": None,
            "original_rate": 0,
            "discounted_rate": 0,
        },
    ]


def test_normalize_redemption_fee_rows_accepts_less_than_or_equal_ranges():
    frame = pd.DataFrame(
        {
            "适用期限": ["小于等于6天", "大于等于7天，小于等于29天", "大于等于730天"],
            "赎回费率": ["1.50%", "0.75%", "0.00%"],
        }
    )

    tiers = normalize_redemption_fee_rows(frame)

    assert tiers == [
        {
            "min_holding_days": 0,
            "max_holding_days": 7,
            "original_rate": 0.015,
            "discounted_rate": 0.015,
        },
        {
            "min_holding_days": 7,
            "max_holding_days": 30,
            "original_rate": 0.0075,
            "discounted_rate": 0.0075,
        },
        {
            "min_holding_days": 730,
            "max_holding_days": None,
            "original_rate": 0,
            "discounted_rate": 0,
        },
    ]


def test_normalize_redemption_fee_rows_accepts_year_ranges():
    frame = pd.DataFrame(
        {
            "适用期限": ["小于7天", "大于等于7天，小于1年", "大于等于1年，小于2年", "大于等于2年"],
            "赎回费率": ["1.50%", "0.20%", "0.05%", "0.00%"],
        }
    )

    tiers = normalize_redemption_fee_rows(frame)

    assert tiers == [
        {
            "min_holding_days": 0,
            "max_holding_days": 7,
            "original_rate": 0.015,
            "discounted_rate": 0.015,
        },
        {
            "min_holding_days": 7,
            "max_holding_days": 365,
            "original_rate": 0.002,
            "discounted_rate": 0.002,
        },
        {
            "min_holding_days": 365,
            "max_holding_days": 730,
            "original_rate": 0.0005,
            "discounted_rate": 0.0005,
        },
        {
            "min_holding_days": 730,
            "max_holding_days": None,
            "original_rate": 0,
            "discounted_rate": 0,
        },
    ]


def test_normalize_purchase_fee_rows_rejects_unparseable_tier():
    frame = pd.DataFrame(
        {
            "适用金额": ["详见基金公告"],
            "原费率": ["1.50%"],
            "天天基金优惠费率": ["0.15%"],
        }
    )

    with pytest.raises(DataSourceError, match="Failed to parse purchase fee tier"):
        normalize_purchase_fee_rows(frame)


def test_normalize_fund_info_combines_profile_status_fees_and_rating():
    basic_frame = pd.DataFrame(
        {
            "item": ["基金名称", "基金类型", "成立时间", "最新规模", "管理费率"],
            "value": ["银河领先债券C", "债券型", "2023-01-01", "10.25亿元", "0.30%/年"],
        }
    )
    purchase_status_frame = pd.DataFrame(
        {
            "基金代码": ["017763"],
            "申购状态": ["开放申购"],
            "赎回状态": ["开放赎回"],
        }
    )
    purchase_fee_frame = pd.DataFrame(
        {
            "适用金额": ["小于100万元"],
            "原费率": ["1.50%"],
            "天天基金优惠费率": ["0.15%"],
        }
    )
    redemption_fee_frame = pd.DataFrame(
        {
            "持有期限": ["小于7天"],
            "赎回费率": ["1.50%"],
        }
    )
    rating_frame = pd.DataFrame(
        {
            "代码": ["017763"],
            "晨星评级": ["5"],
        }
    )

    result = normalize_fund_info(
        "017763",
        basic_frame,
        purchase_status_frame,
        purchase_fee_frame,
        redemption_fee_frame,
        rating_frame,
        updated_at="2026-06-07T12:00:00+00:00",
    )

    assert result.code == "017763"
    assert result.name == "银河领先债券C"
    assert result.fund_type == "债券型"
    assert result.established_date == "2023-01-01"
    assert result.asset_size == "10.25亿元"
    assert result.operation_fee == OperationFee(management_fee=0.003)
    assert result.purchase_status == "开放申购"
    assert result.purchase_limit_amount is None
    assert result.redemption_status == "开放赎回"
    assert result.morningstar_rating == "5"
    assert result.purchase_fee[0]["discounted_rate"] == 0.0015
    assert result.redemption_fee[0]["original_rate"] == 0.015
    assert result.source == "akshare"
    assert result.updated_at == "2026-06-07T12:00:00+00:00"


def test_normalize_fund_info_reads_daily_purchase_limit():
    basic_frame = pd.DataFrame(
        {
            "item": ["基金名称"],
            "value": ["华宝纳斯达克精选股票发起式(QDII)A"],
        }
    )
    purchase_status_frame = pd.DataFrame(
        {
            "基金代码": ["017436"],
            "申购状态": ["限大额"],
            "赎回状态": ["开放赎回"],
            "日累计限定金额": [1000.0],
        }
    )

    result = normalize_fund_info(
        "017436",
        basic_frame,
        purchase_status_frame,
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        updated_at="2026-06-07T12:00:00+00:00",
    )

    assert result.purchase_status == "限大额"
    assert result.purchase_limit_amount == 1000.0


def test_normalize_fund_info_ignores_unlimited_purchase_limit_sentinel():
    basic_frame = pd.DataFrame(
        {
            "item": ["基金名称"],
            "value": ["银河领先债券C"],
        }
    )
    purchase_status_frame = pd.DataFrame(
        {
            "基金代码": ["017763"],
            "申购状态": ["开放申购"],
            "赎回状态": ["开放赎回"],
            "日累计限定金额": [100000000000.0],
        }
    )

    result = normalize_fund_info(
        "017763",
        basic_frame,
        purchase_status_frame,
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        updated_at="2026-06-07T12:00:00+00:00",
    )

    assert result.purchase_status == "开放申购"
    assert result.purchase_limit_amount is None


@pytest.mark.parametrize("purchase_status", ["暂停申购", "封闭期", "场内交易", "认购期", ""])
def test_normalize_fund_info_sets_zero_purchase_limit_when_buying_unavailable(purchase_status):
    basic_frame = pd.DataFrame(
        {
            "item": ["基金名称"],
            "value": ["易方达信用债债券A"],
        }
    )
    purchase_status_frame = pd.DataFrame(
        {
            "基金代码": ["000032"],
            "申购状态": [purchase_status],
            "赎回状态": ["开放赎回"],
            "日累计限定金额": [100000000000.0],
        }
    )

    result = normalize_fund_info(
        "000032",
        basic_frame,
        purchase_status_frame,
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        updated_at="2026-06-07T12:00:00+00:00",
    )

    assert result.purchase_status == (purchase_status or None)
    assert result.purchase_limit_amount == 0


def test_fetch_fund_info_aggregates_akshare_frames():
    calls = []

    def basic_fetcher(symbol):
        calls.append(("basic", symbol))
        return pd.DataFrame(
            {
                "item": ["基金名称", "基金类型", "成立时间", "最新规模"],
                "value": ["银河领先债券C", "债券型", "2023-01-01", "10.25亿元"],
            }
        )

    def purchase_fetcher():
        calls.append(("purchase_status", None))
        return pd.DataFrame(
            {
                "基金代码": ["017763"],
                "申购状态": ["开放申购"],
                "赎回状态": ["开放赎回"],
            }
        )

    def fee_fetcher(symbol, indicator):
        calls.append(("fee", symbol, indicator))
        if indicator == "申购费率（前端）":
            return pd.DataFrame(
                {
                    "适用金额": ["小于100万元"],
                    "原费率": ["1.50%"],
                    "天天基金优惠费率": ["0.15%"],
                }
            )
        return pd.DataFrame(
            {
                "适用期限": ["小于7天", "大于等于7天，小于30天"],
                "赎回费率": ["1.50%", "0.10%"],
            }
        )

    def rating_fetcher():
        calls.append(("rating", None))
        return pd.DataFrame({"代码": ["017763"], "晨星评级": ["5"]})

    result = fetch_fund_info(
        "017763",
        basic_fetcher=basic_fetcher,
        purchase_fetcher=purchase_fetcher,
        fee_fetcher=fee_fetcher,
        rating_fetcher=rating_fetcher,
        clock=lambda: "2026-06-07T12:00:00+00:00",
    )

    assert result.name == "银河领先债券C"
    assert result.established_date == "2023-01-01"
    assert result.asset_size == "10.25亿元"
    assert result.purchase_status == "开放申购"
    assert result.morningstar_rating == "5"
    assert result.purchase_fee[0]["max_amount"] == 1000000
    assert result.redemption_fee[0]["max_holding_days"] == 7
    assert calls == [
        ("basic", "017763"),
        ("purchase_status", None),
        ("fee", "017763", "申购费率（前端）"),
        ("fee", "017763", "赎回费率"),
        ("rating", None),
    ]


def test_fetch_fund_info_falls_back_to_eastmoney_purchase_fee_table():
    calls = []

    def basic_fetcher(symbol):
        return pd.DataFrame(
            {
                "item": ["基金名称"],
                "value": ["华宝纳斯达克精选股票发起式(QDII)A"],
            }
        )

    def purchase_fetcher():
        return pd.DataFrame(
            {
                "基金代码": ["017436"],
                "申购状态": ["限大额"],
                "赎回状态": ["开放赎回"],
                "日累计限定金额": [1000.0],
            }
        )

    def fee_fetcher(symbol, indicator):
        calls.append(("fee", symbol, indicator))
        if indicator == "申购费率（前端）":
            raise KeyError(indicator)
        return pd.DataFrame({"适用期限": ["小于7天"], "赎回费率": ["1.50%"]})

    def fee_page_fetcher(url):
        calls.append(("fee_page", url))
        return """
        <html><body>
        <h4 class="t">交易状态</h4><table><tr><td>申购状态</td><td>限大额</td></tr></table>
        <h4 class="t"><label class="left">运作费用</label><label class="right"></label></h4>
        <table>
          <tr><td>管理费率</td><td>0.50%（每年）</td><td>托管费率</td><td>0.10%（每年）</td><td>销售服务费率</td><td>0.00%（每年）</td></tr>
        </table>
        <h4 class="t"><label class="left">申购费率</label><label class="right"></label></h4>
        <table>
          <tr><th>适用金额</th><th>原费率|天天基金优惠费率</th></tr>
          <tr><td>小于100万元</td><td>1.50% | 0.15%</td></tr>
          <tr><td>大于等于100万元，小于200万元</td><td>1.00% | 0.10%</td></tr>
          <tr><td>大于等于200万元</td><td>每笔1000元</td></tr>
        </table>
        <h4 class="t">赎回费率</h4><table><tr><td>小于7天</td><td>1.50%</td></tr></table>
        </body></html>
        """

    result = fetch_fund_info(
        "017436",
        basic_fetcher=basic_fetcher,
        purchase_fetcher=purchase_fetcher,
        fee_fetcher=fee_fetcher,
        rating_fetcher=lambda: pd.DataFrame(),
        fee_page_fetcher=fee_page_fetcher,
        clock=lambda: "2026-06-07T12:00:00+00:00",
    )

    assert result.purchase_limit_amount == 1000.0
    assert result.operation_fee == OperationFee(
        management_fee=0.005,
        custodian_fee=0.001,
        sales_service_fee=0.0,
    )
    assert result.operation_fee.total == 0.006
    assert result.purchase_fee == [
        {
            "min_amount": 0,
            "max_amount": 1000000,
            "original_rate": 0.015,
            "discounted_rate": 0.0015,
        },
        {
            "min_amount": 1000000,
            "max_amount": 2000000,
            "original_rate": 0.01,
            "discounted_rate": 0.001,
        },
        {
            "min_amount": 2000000,
            "max_amount": None,
            "original_rate": None,
            "discounted_rate": None,
            "fixed_fee": 1000,
        },
    ]
    assert calls == [
        ("fee", "017436", "申购费率（前端）"),
        ("fee_page", "https://fundf10.eastmoney.com/jjfl_017436.html"),
        ("fee", "017436", "赎回费率"),
    ]


def test_fund_basic_frame_from_eastmoney_html_parses_profile_table():
    html = """
    <html><body>
    <table>
      <tr><th>基金全称</th><td>百嘉中证同业存单AAA指数7天持有期证券投资基金</td><th>基金简称</th><td>百嘉中证同业存单AAA指数7天持有</td></tr>
      <tr><th>基金代码</th><td>017725（前端）</td><th>基金类型</th><td>指数型-固收</td></tr>
      <tr><th>发行日期</th><td>2023年03月01日</td><th>成立日期/规模</th><td>2023年03月16日 / 11.957亿份</td></tr>
      <tr><th>净资产规模</th><td>0.07亿元（截止至：2026年03月31日）</td><th>份额规模</th><td>0.0653亿份</td></tr>
    </table>
    </body></html>
    """

    frame = _fund_basic_frame_from_eastmoney_html(html)

    assert frame.to_dict("records") == [
        {"item": "基金代码", "value": "017725"},
        {"item": "基金名称", "value": "百嘉中证同业存单AAA指数7天持有"},
        {"item": "基金类型", "value": "指数型-固收"},
        {"item": "成立时间", "value": "2023-03-16"},
        {"item": "最新规模", "value": "0.07亿元"},
    ]


def test_fetch_fund_info_falls_back_to_eastmoney_basic_profile():
    calls = []

    def basic_fetcher(symbol):
        calls.append(("basic", symbol))
        raise KeyError("data")

    def purchase_fetcher():
        return pd.DataFrame(
            {
                "基金代码": ["017725"],
                "申购状态": ["限大额"],
                "赎回状态": ["开放赎回"],
                "日累计限定金额": [10000000.0],
            }
        )

    def fee_fetcher(symbol, indicator):
        return pd.DataFrame()

    def basic_page_fetcher(url):
        calls.append(("basic_page", url))
        return """
        <html><body>
        <table>
          <tr><th>基金全称</th><td>百嘉中证同业存单AAA指数7天持有期证券投资基金</td><th>基金简称</th><td>百嘉中证同业存单AAA指数7天持有</td></tr>
          <tr><th>基金代码</th><td>017725（前端）</td><th>基金类型</th><td>指数型-固收</td></tr>
          <tr><th>发行日期</th><td>2023年03月01日</td><th>成立日期/规模</th><td>2023年03月16日 / 11.957亿份</td></tr>
          <tr><th>净资产规模</th><td>0.07亿元（截止至：2026年03月31日）</td><th>份额规模</th><td>0.0653亿份</td></tr>
        </table>
        </body></html>
        """

    result = fetch_fund_info(
        "017725",
        basic_fetcher=basic_fetcher,
        purchase_fetcher=purchase_fetcher,
        fee_fetcher=fee_fetcher,
        basic_page_fetcher=basic_page_fetcher,
        fee_page_fetcher=lambda url: "",
        rating_fetcher=lambda: pd.DataFrame(),
        clock=lambda: "2026-06-07T12:00:00+00:00",
    )

    assert result.name == "百嘉中证同业存单AAA指数7天持有"
    assert result.fund_type == "指数型-固收"
    assert result.established_date == "2023-03-16"
    assert result.asset_size == "0.07亿元"
    assert result.purchase_status == "限大额"
    assert result.purchase_limit_amount == 10000000.0
    assert calls == [
        ("basic", "017725"),
        ("basic_page", "https://fundf10.eastmoney.com/jbgk_017725.html"),
    ]


def test_operation_fee_from_eastmoney_html_treats_missing_sales_service_fee_as_zero():
    html = """
    <html><body>
    <h4 class="t"><label class="left">运作费用</label><label class="right"></label></h4>
    <table>
      <tr><td>管理费率</td><td>0.80%（每年）</td><td>托管费率</td><td>0.20%（每年）</td><td>销售服务费率</td><td>---</td></tr>
    </table>
    </body></html>
    """

    result = _operation_fee_from_eastmoney_html(html)

    assert result == OperationFee(
        management_fee=0.008,
        custodian_fee=0.002,
        sales_service_fee=0.0,
    )
    assert result.total == 0.01


@pytest.mark.parametrize("date_value", [None, pd.NA, "", float("nan")])
def test_normalize_gold_rows_rejects_missing_dates(date_value):
    frame = pd.DataFrame({"日期": [date_value], "收盘价": [530.5]})

    with pytest.raises(DataSourceError):
        normalize_gold_rows(frame)


@pytest.mark.parametrize("numeric_value", [None, pd.NA, "", float("nan")])
def test_normalize_gold_rows_rejects_missing_numeric_values(numeric_value):
    frame = pd.DataFrame({"日期": ["2026-04-17"], "收盘价": [numeric_value]})

    with pytest.raises(DataSourceError):
        normalize_gold_rows(frame)


def test_fetch_text_reads_http_error_body(monkeypatch):
    def urlopen(request, timeout):
        raise HTTPError(
            request.full_url,
            500,
            "Internal Server Error",
            {},
            BytesIO(b"detailPE_data = [[Date.UTC(2026, 4, 1),16.1419],];"),
        )

    monkeypatch.setattr("finance_cli.sources.urlopen", urlopen)

    assert "detailPE_data" in _fetch_text("https://worldperatio.com/area/vietnam/")


def test_fetch_text_decodes_brotli_response(monkeypatch):
    class Response:
        headers = {"Content-Encoding": "br"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b"\x0f\x07\x80<html>ok</html>\x03"

    def urlopen(request, timeout):
        return Response()

    monkeypatch.setattr("finance_cli.sources.urlopen", urlopen)

    assert _fetch_text("https://www.etf.run/index/CSI/930707") == "<html>ok</html>"


def test_fetch_index_pe_rows_uses_injected_danjuan_fetcher():
    calls = []

    def fetcher():
        calls.append("fetch")
        return json.dumps(
            {
                "data": {
                    "index_eva_pe_growths": [
                        {"pe": 12.3, "ts": 1744848000000},
                    ]
                },
                "result_code": 0,
            }
        )

    rows = fetch_index_pe_rows("000300", fetcher=fetcher)

    assert calls == ["fetch"]
    assert rows[0].asset_type == "index"
    assert rows[0].code == "000300"
    assert rows[0].metric == "rolling_pe"
    assert rows[0].value == 12.3
    assert rows[0].source == "danjuan"


def test_fetch_index_pe_rows_normalizes_exchange_prefixed_code():
    calls = []

    def fetcher():
        calls.append("fetch")
        return json.dumps(
            {
                "data": {
                    "index_eva_pe_growths": [
                        {"pe": 12.3, "ts": 1744848000000},
                    ]
                },
                "result_code": 0,
            }
        )

    rows = fetch_index_pe_rows("SH000300", fetcher=fetcher)

    assert calls == ["fetch"]
    assert rows[0].code == "000300"
    assert rows[0].source == "danjuan"


def test_fetch_index_pe_rows_accepts_h_prefixed_csindex_code():
    calls = []

    def fetcher():
        calls.append("fetch")
        return json.dumps(
            {
                "data": {
                    "index_eva_pe_growths": [
                        {"pe": 7.82, "ts": 1748476800000},
                    ]
                },
                "result_code": 0,
            }
        )

    rows = fetch_index_pe_rows("H30269", fetcher=fetcher)

    assert calls == ["fetch"]
    assert rows[0].code == "H30269"
    assert rows[0].value == 7.82
    assert rows[0].source == "danjuan"


def test_fetch_index_pe_rows_supports_ndx_from_worldperatio_source():
    calls = []

    def fetcher():
        calls.append("fetch")
        return """
        {
            "data": {
                "index_eva_pe_growths": [
                    {"pe": 22.9024, "ts": 1463932800000},
                    {"pe": 35.1883, "ts": 1779379200000}
                ]
            },
            "result_code": 0
        }
        """

    rows = fetch_index_pe_rows("NDX", fetcher=fetcher)

    assert calls == ["fetch"]
    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("index", "NDX", "rolling_pe", "2016-05-23", 22.9024, "danjuan"),
        ("index", "NDX", "rolling_pe", "2026-05-22", 35.1883, "danjuan"),
    ]


def test_fetch_index_pe_rows_supports_sp500_from_danjuan_source():
    calls = []

    def fetcher():
        calls.append("fetch")
        return """
        {
            "data": {
                "index_eva_pe_growths": [
                    {"pe": 23.1982, "ts": 1465142400000},
                    {"pe": 28.2749, "ts": 1780588800000}
                ]
            },
            "result_code": 0
        }
        """

    rows = fetch_index_pe_rows("SP500", fetcher=fetcher)

    assert calls == ["fetch"]
    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("index", "SP500", "rolling_pe", "2016-06-06", 23.1982, "danjuan"),
        ("index", "SP500", "rolling_pe", "2026-06-05", 28.2749, "danjuan"),
    ]


def test_normalize_danjuan_ndx_pe_rows_rejects_error_response():
    with pytest.raises(DataSourceError, match="Danjuan PE data request failed"):
        normalize_danjuan_index_pe_rows("NDX", '{"result_code": 1, "message": "failed"}')


def test_normalize_danjuan_ndx_pe_rows_rejects_missing_series():
    with pytest.raises(DataSourceError, match="No Danjuan PE data found"):
        normalize_danjuan_index_pe_rows("NDX", '{"data": {}, "result_code": 0}')


def test_normalize_danjuan_ndx_pe_rows_rejects_empty_series():
    with pytest.raises(DataSourceError, match="No Danjuan PE data found"):
        normalize_danjuan_index_pe_rows("NDX", '{"data": {"index_eva_pe_growths": []}, "result_code": 0}')


def test_fetch_index_pe_rows_supports_vn30_from_worldperatio_source():
    calls = []

    def fetcher():
        calls.append("fetch")
        return "detailPE_data = [[Date.UTC(2026, 3, 1),15.5773],[Date.UTC(2026, 4, 1),16.1419],];"

    rows = fetch_index_pe_rows("VN30", fetcher=fetcher)

    assert calls == ["fetch"]
    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("index", "VN30", "rolling_pe", "2026-04-01", 15.5773, "worldperatio"),
        ("index", "VN30", "rolling_pe", "2026-05-01", 16.1419, "worldperatio"),
    ]


def test_normalize_worldperatio_pe_rows_rejects_missing_series():
    with pytest.raises(DataSourceError, match="No WorldPEratio PE data found for VN30"):
        normalize_worldperatio_pe_rows("VN30", "<html></html>")


def test_normalize_ndx_pe_rows_rejects_missing_worldperatio_series():
    with pytest.raises(DataSourceError, match="No NDX PE data found"):
        normalize_ndx_pe_rows("<html></html>")


def test_normalize_index_pe_code_accepts_ndx_case_insensitively():
    assert normalize_index_pe_code("ndx") == "NDX"


def test_normalize_index_pe_code_accepts_sp500_case_insensitively():
    assert normalize_index_pe_code("sp500") == "SP500"


def test_normalize_index_pe_code_accepts_vn30_case_insensitively():
    assert normalize_index_pe_code("vn30") == "VN30"


def test_normalize_csindex_code_accepts_h_prefixed_indicator_code():
    assert normalize_csindex_code("h30269") == "H30269"


def test_normalize_csindex_code_rejects_invalid_code():
    with pytest.raises(DataSourceError, match="Invalid index code"):
        normalize_csindex_code("SH300")


def test_to_danjuan_index_code_sh_maps_shanghai():
    assert _to_danjuan_index_code("000300") == "SH000300"
    assert _to_danjuan_index_code("000016") == "SH000016"


def test_to_danjuan_index_code_sz_maps_shenzhen():
    assert _to_danjuan_index_code("399967") == "SZ399967"
    assert _to_danjuan_index_code("399905") == "SZ399905"


def test_to_danjuan_index_code_passes_through_unknown_prefix():
    assert _to_danjuan_index_code("H30269") == "H30269"
    assert _to_danjuan_index_code("NDX") == "NDX"


def test_fetch_gold_rows_uses_injected_fetcher_without_network():
    calls = []

    def fetcher(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame({"日期": ["2026-04-17"], "收盘价": [530.5]})

    rows = fetch_gold_rows(fetcher=fetcher)

    assert calls == [{"symbol": "Au99.99"}]
    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("gold", "AU9999", "close", "2026-04-17", 530.5, "akshare"),
    ]


def test_fetch_index_value_rows_uses_injected_fetcher_for_imci():
    seen = {}
    payload = {
        "上期所有色金屬價格指數(IMCI)": {
            "data": {"2026-06-11T16:00:00.000Z": "5410.94"}
        }
    }

    def fetcher(url):
        seen["url"] = url
        return json.dumps(payload)

    rows = fetch_index_value_rows("imci", fetcher=fetcher)

    assert "fields=3271" in seen["url"]
    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("index", "IMCI", "price_index", "2026-06-12", 5410.94, "trendforce"),
    ]


def test_fetch_fund_nav_rows_uses_unit_nav_indicator_by_default():
    calls = []

    def fetcher(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame({"净值日期": ["2026-05-22"], "单位净值": [1.2456]})

    rows = fetch_fund_nav_rows("017763", fetcher=fetcher)

    assert calls == [{"symbol": "017763", "indicator": "单位净值走势", "period": "成立来"}]
    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("fund", "017763", "unit_nav", "2026-05-22", 1.2456, "akshare"),
    ]


def test_fetch_fund_nav_rows_uses_accumulated_nav_indicator():
    calls = []

    def fetcher(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame({"净值日期": ["2026-05-22"], "累计净值": [1.9876]})

    rows = fetch_fund_nav_rows("017763", nav_type="accumulated", fetcher=fetcher)

    assert calls == [{"symbol": "017763", "indicator": "累计净值走势", "period": "成立来"}]
    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("fund", "017763", "accumulated_nav", "2026-05-22", 1.9876, "akshare"),
    ]


def test_fetch_fund_is_money_fund_reads_eastmoney_ishb_flag():
    seen = []

    def fetcher(url):
        seen.append(url)
        return 'var fS_code = "001821";var ishb=true;'

    assert fetch_fund_is_money_fund("001821", fetcher=fetcher) is True
    assert seen == ["https://fund.eastmoney.com/pingzhongdata/001821.js"]


def test_fetch_money_fund_rows_uses_money_fund_fetcher():
    calls = []

    def fetcher(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame(
            {
                "净值日期": ["2026-06-07"],
                "每万份收益": [0.3571],
                "7日年化收益率": [1.342],
            }
        )

    rows = fetch_money_fund_rows("001821", fetcher=fetcher)

    assert calls == [{"symbol": "001821"}]
    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("fund", "001821", "million_copies_income", "2026-06-07", 0.3571, "akshare"),
        ("fund", "001821", "seven_day_annualized_yield", "2026-06-07", 1.342, "akshare"),
    ]


def test_normalize_index_dividend_yield_rows_prefers_documented_calculation_share_yield():
    frame = pd.DataFrame(
        {
            "日期": ["2026-04-17"],
            "股息率1": [2.8],
            "股息率2": [3.1],
        }
    )

    rows = normalize_index_dividend_yield_rows("000300", frame)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("index", "000300", "dividend_yield", "2026-04-17", 3.1, "akshare"),
    ]


def test_normalize_index_dividend_yield_rows_accepts_csindex_indicator_columns():
    frame = pd.DataFrame(
        {
            "日期Date": [20260522],
            "股息率1（总股本）D/P1": [4.30],
            "股息率2（计算用股本）D/P2": [4.82],
        }
    )

    rows = normalize_index_dividend_yield_rows("H30269", frame)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("index", "H30269", "dividend_yield", "2026-05-22", 4.82, "akshare"),
    ]


def test_normalize_funddb_index_dividend_yield_rows_parses_highcharts_series():
    payload = {
        "code": 200,
        "data": {
            "series": [
                {
                    "name": "平均值",
                    "data": [[1452211200000, 4.73]],
                },
                {
                    "name": "股息率",
                    "data": [
                        [1452211200000, 3.15],
                        [1452297600000, None],
                        [1452384000000, "3.18"],
                    ],
                }
            ]
        },
    }

    rows = normalize_funddb_index_dividend_yield_rows("000922", payload)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("index", "000922", "dividend_yield", "2016-01-08", 3.15, "funddb"),
        ("index", "000922", "dividend_yield", "2016-01-10", 3.18, "funddb"),
    ]


def test_merge_index_dividend_yield_rows_prefers_current_source_on_duplicate_dates():
    historical_rows = [
        DailyMetric("index", "000922", "dividend_yield", "2026-05-12", 3.8, "funddb"),
        DailyMetric("index", "000922", "dividend_yield", "2026-05-13", 3.9, "funddb"),
    ]
    current_rows = [
        DailyMetric("index", "000922", "dividend_yield", "2026-05-13", 4.1, "akshare"),
        DailyMetric("index", "000922", "dividend_yield", "2026-05-14", 4.2, "akshare"),
    ]

    rows = merge_index_dividend_yield_rows(current_rows, historical_rows)

    assert [(row.date, row.value, row.source) for row in rows] == [
        ("2026-05-12", 3.8, "funddb"),
        ("2026-05-13", 4.1, "akshare"),
        ("2026-05-14", 4.2, "akshare"),
    ]


def test_normalize_index_pb_rows_from_etf_run_reads_latest_pb():
    html = """
    # 中证畜牧
    <span>更新至 <!-- -->2026/05/22</span>
    ## 市净率
    <span>最新市净率</span><span>2.23</span>
    """

    rows = normalize_index_pb_rows_from_etf_run("930707", html)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("index", "930707", "pb", "2026-05-22", 2.23, "etf.run"),
    ]


def test_normalize_index_pb_rows_from_etf_run_reads_compressed_history():
    html = r'''
    <script>
    self.__next_f.push([1,"{\"compressedIndexDaily\":{\"fieldNames\":[\"date\",\"tradeAt\",\"close\",\"equalWeightedPeTtm\",\"historyPePercentile\",\"equalWeightedPbTtm\",\"historyPbPercentile\"],\"values\":[[\"2021-02-22\",1613923200000,4087.0469,22.59,1,3.299,1],[\"2026-05-22\",1747872000000,10975.57,35.8981,0.3,2.2344,0.286164]]}}"])
    </script>
    '''

    rows = normalize_index_pb_rows_from_etf_run("930707", html)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("index", "930707", "pb", "2021-02-22", 3.299, "etf.run"),
        ("index", "930707", "pb", "2026-05-22", 2.2344, "etf.run"),
    ]


def test_fetch_index_pb_rows_uses_etf_run_csi_page():
    calls = []

    def fetcher(url):
        calls.append(url)
        return r'''
        <script>
        self.__next_f.push([1,"{\"compressedIndexDaily\":{\"fieldNames\":[\"date\",\"equalWeightedPbTtm\"],\"values\":[[\"2021-02-22\",3.299],[\"2026-05-22\",2.2344]]}}"])
        </script>
        '''

    rows = fetch_index_pb_rows("930707", fetcher=fetcher)

    assert calls == ["https://www.etf.run/index/CSI/930707"]
    assert [(row.code, row.date, row.value) for row in rows] == [
        ("930707", "2021-02-22", 3.299),
        ("930707", "2026-05-22", 2.2344),
    ]



def test_fetch_index_dividend_yield_rows_filters_to_latest_date_on_or_before_query_date():
    calls = []

    def fetcher(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame(
            {
                "日期": ["2026-04-17", "2026-04-20", "2026-04-21"],
                "股息率2": [3.1, 3.2, 3.3],
            }
        )

    rows = fetch_index_dividend_yield_rows("000300", query_date="2026-04-20", fetcher=fetcher)

    assert calls == [{"symbol": "000300"}]
    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("index", "000300", "dividend_yield", "2026-04-20", 3.2, "akshare"),
    ]


def test_fetch_index_dividend_yield_rows_combines_history_when_history_fetcher_is_provided():
    def current_fetcher(**kwargs):
        return pd.DataFrame({"日期": ["2026-05-13"], "股息率2": [4.1]})

    def history_fetcher(code):
        return [DailyMetric("index", code, "dividend_yield", "2016-01-08", 3.15, "funddb")]

    rows = fetch_index_dividend_yield_rows(
        "SH000922",
        fetcher=current_fetcher,
        history_fetcher=history_fetcher,
    )

    assert [(row.code, row.date, row.value, row.source) for row in rows] == [
        ("000922", "2016-01-08", 3.15, "funddb"),
        ("000922", "2026-05-13", 4.1, "akshare"),
    ]


def test_fetch_index_dividend_yield_history_rows_uses_funddb_payload_fetcher():
    calls = []

    def fetcher(params):
        calls.append(params)
        return {
            "data": {
                "series": [
                    {"name": "股息率", "data": [[1452211200000, 3.15]]},
                ]
            }
        }

    rows = fetch_index_dividend_yield_history_rows("SH000922", fetcher=fetcher)

    assert calls == [{"gu_code": "000922.CSI", "pe_category": "xilv", "year": "10", "ver": "new"}]
    assert [(row.code, row.date, row.value, row.source) for row in rows] == [
        ("000922", "2016-01-08", 3.15, "funddb"),
    ]


def test_fetch_index_dividend_yield_history_rows_falls_back_to_sh_suffix_for_000_codes():
    calls = []

    def fetcher(params):
        calls.append(params)
        if params["gu_code"] == "000016.CSI":
            return {"data": {"tubiao": {}}}
        return {
            "data": {
                "tubiao": {
                    "series": [
                        {"name": "股息率", "data": [[1452211200000, 2.15]]},
                    ]
                }
            }
        }

    rows = fetch_index_dividend_yield_history_rows("000016", fetcher=fetcher)

    assert [call["gu_code"] for call in calls] == ["000016.CSI", "000016.SH"]
    assert [(row.code, row.date, row.value, row.source) for row in rows] == [
        ("000016", "2016-01-08", 2.15, "funddb"),
    ]


def test_fetch_index_dividend_yield_rows_without_query_date_returns_all_rows():
    def fetcher(**kwargs):
        return pd.DataFrame({"日期": ["2026-04-17", "2026-04-20"], "股息率2": [3.1, 3.2]})

    rows = fetch_index_dividend_yield_rows("000300", fetcher=fetcher)

    assert [row.date for row in rows] == ["2026-04-17", "2026-04-20"]


def test_normalize_sw_index_pb_rows_filters_code_and_reads_pb():
    frame = pd.DataFrame(
        {
            "发布日期": ["2026-04-17", "2026-04-17"],
            "指数代码": ["801010", "801020"],
            "市净率": [1.8, 2.3],
        }
    )

    rows = normalize_sw_index_pb_rows("801010", "一级行业", frame)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("sw_index:一级行业", "801010", "pb", "2026-04-17", 1.8, "akshare"),
    ]


def test_normalize_sw_index_pb_rows_rejects_missing_code():
    frame = pd.DataFrame({"日期": ["2026-04-17"], "指数代码": ["801020"], "市净率": [2.3]})

    with pytest.raises(DataSourceError, match="No PB data"):
        normalize_sw_index_pb_rows("801010", "一级行业", frame)


def test_fetch_sw_index_pb_rows_uses_injected_fetcher_with_query_date():
    calls = []

    def fetcher(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame({"发布日期": ["2026-04-17"], "指数代码": ["801010"], "市净率": [1.8]})

    rows = fetch_sw_index_pb_rows("801010", "一级行业", query_date="2026-04-17", fetcher=fetcher)

    assert calls == [{"symbol": "一级行业", "start_date": "20260407", "end_date": "20260417"}]
    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("sw_index:一级行业", "801010", "pb", "2026-04-17", 1.8, "akshare"),
    ]


def test_fetch_sw_index_pb_rows_wraps_akshare_empty_result_key_error():
    def fetcher(**kwargs):
        raise KeyError("发布日期")

    with pytest.raises(DataSourceError, match="No SW index PB data available on or before 2026-05-22"):
        fetch_sw_index_pb_rows("801010", "一级行业", query_date="2026-05-22", fetcher=fetcher)


def test_fetch_sw_index_pb_rows_reports_code_missing_from_category():
    def fetcher(**kwargs):
        return pd.DataFrame({"发布日期": ["2026-05-20"], "指数代码": ["801010"], "市净率": [2.38]})

    with pytest.raises(DataSourceError, match="No PB data found for SW index 000300 in 一级行业"):
        fetch_sw_index_pb_rows("000300", "一级行业", query_date="2026-05-22", fetcher=fetcher)


def test_fetch_sw_index_pb_rows_without_query_date_keeps_history_sync_window():
    calls = []

    def fetcher(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame({"发布日期": ["2026-04-17"], "指数代码": ["801010"], "市净率": [1.8]})

    fetch_sw_index_pb_rows("801010", "一级行业", fetcher=fetcher)

    assert calls == [{"symbol": "一级行业", "start_date": "19900101", "end_date": date.today().strftime("%Y%m%d")}]


def test_normalize_cn10y_yield_rows_reads_china_10y_column():
    frame = pd.DataFrame(
        {
            "日期": ["2026-04-17", "2026-04-20"],
            "中国国债收益率10年": [1.7, 1.8],
        }
    )

    rows = normalize_cn10y_yield_rows(frame)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("bond", "CN10Y", "yield", "2026-04-17", 1.7, "akshare"),
        ("bond", "CN10Y", "yield", "2026-04-20", 1.8, "akshare"),
    ]


def test_normalize_cn10y_yield_rows_skips_missing_yields():
    frame = pd.DataFrame(
        {
            "日期": ["1990-12-19", "2026-05-21"],
            "中国国债收益率10年": [float("nan"), 1.7448],
        }
    )

    rows = normalize_cn10y_yield_rows(frame)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("bond", "CN10Y", "yield", "2026-05-21", 1.7448, "akshare"),
    ]


def test_normalize_cn10y_yield_rows_rejects_all_missing_yields():
    frame = pd.DataFrame(
        {
            "日期": ["1990-12-19"],
            "中国国债收益率10年": [float("nan")],
        }
    )

    with pytest.raises(DataSourceError, match="No valid CN10Y yield data"):
        normalize_cn10y_yield_rows(frame)


def test_fetch_cn10y_yield_rows_uses_injected_fetcher_without_network():
    calls = []

    def fetcher(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame({"日期": ["2026-04-17"], "中国国债收益率10年": [1.7]})

    rows = fetch_cn10y_yield_rows(fetcher=fetcher)

    assert calls == [{"start_date": "19901219"}]
    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("bond", "CN10Y", "yield", "2026-04-17", 1.7, "akshare"),
    ]


def test_fetch_us10y_tips_yield_rows_parses_treasury_xml():
    def fetcher(url):
        if url.endswith("page=1"):
            return """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"></feed>"""
        assert url.endswith("field_tdr_date_value=all&page=0")
        return """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices"
      xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
      xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <content type="application/xml">
      <m:properties>
        <d:NEW_DATE m:type="Edm.DateTime">2026-06-08T00:00:00</d:NEW_DATE>
        <d:TC_10YEAR m:type="Edm.Double">2.21</d:TC_10YEAR>
      </m:properties>
    </content>
  </entry>
  <entry>
    <content type="application/xml">
      <m:properties>
        <d:NEW_DATE m:type="Edm.DateTime">2026-06-09T00:00:00</d:NEW_DATE>
        <d:TC_10YEAR m:type="Edm.Double">2.20</d:TC_10YEAR>
      </m:properties>
    </content>
  </entry>
</feed>"""

    rows = fetch_us10y_tips_yield_rows(fetcher=fetcher)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("bond", "US10Y_TIPS", "yield", "2026-06-08", 2.21, "treasury"),
        ("bond", "US10Y_TIPS", "yield", "2026-06-09", 2.20, "treasury"),
    ]


def test_fetch_us10y_tips_yield_rows_skips_missing_values():
    def fetcher(url):
        if url.endswith("page=1"):
            return """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"></feed>"""
        return """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices"
      xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
      xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <content type="application/xml">
      <m:properties>
        <d:NEW_DATE m:type="Edm.DateTime">2026-06-08T00:00:00</d:NEW_DATE>
        <d:TC_10YEAR m:type="Edm.Double"></d:TC_10YEAR>
      </m:properties>
    </content>
  </entry>
  <entry>
    <content type="application/xml">
      <m:properties>
        <d:NEW_DATE m:type="Edm.DateTime">2026-06-10T00:00:00</d:NEW_DATE>
        <d:TC_10YEAR m:type="Edm.Double">2.21</d:TC_10YEAR>
      </m:properties>
    </content>
  </entry>
</feed>"""

    rows = fetch_us10y_tips_yield_rows(fetcher=fetcher)

    assert [(row.date, row.value) for row in rows] == [("2026-06-10", 2.21)]


def test_fetch_us10y_tips_yield_rows_raises_on_missing_value_column():
    def fetcher(url):
        return """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices"
      xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
      xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <content type="application/xml">
      <m:properties>
        <d:NEW_DATE m:type="Edm.DateTime">2026-06-10T00:00:00</d:NEW_DATE>
      </m:properties>
    </content>
  </entry>
</feed>"""

    with pytest.raises(DataSourceError, match="TC_10YEAR field not found"):
        fetch_us10y_tips_yield_rows(fetcher=fetcher)


def test_fetch_us10y_tips_yield_rows_raises_on_empty_data():
    def fetcher(url):
        if url.endswith("page=1"):
            return """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"></feed>"""
        return """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices"
      xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
      xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <content type="application/xml">
      <m:properties>
        <d:NEW_DATE m:type="Edm.DateTime">2026-06-08T00:00:00</d:NEW_DATE>
        <d:TC_10YEAR m:type="Edm.Double"></d:TC_10YEAR>
      </m:properties>
    </content>
  </entry>
</feed>"""

    with pytest.raises(DataSourceError, match="No valid US10Y TIPS yield data"):
        fetch_us10y_tips_yield_rows(fetcher=fetcher)


def test_fetch_us10y_tips_yield_rows_uses_injected_fetcher_without_network():
    calls = []

    def fetcher(url):
        calls.append(url)
        if url.endswith("page=0"):
            return """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices"
      xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
      xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <content type="application/xml">
      <m:properties>
        <d:NEW_DATE m:type="Edm.DateTime">2026-06-10T00:00:00</d:NEW_DATE>
        <d:TC_10YEAR m:type="Edm.Double">2.21</d:TC_10YEAR>
      </m:properties>
    </content>
  </entry>
</feed>"""
        return """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"></feed>"""

    rows = fetch_us10y_tips_yield_rows(fetcher=fetcher)

    assert calls == [
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_real_yield_curve&field_tdr_date_value=all&page=0",
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_real_yield_curve&field_tdr_date_value=all&page=1",
    ]
    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("bond", "US10Y_TIPS", "yield", "2026-06-10", 2.21, "treasury"),
    ]


# ── M2 / Gold USD / Ratio tests ──


FED_H6_CSV_HEADER = (
    '"Series Description","M1; Not seasonally adjusted","M2; Not seasonally adjusted",'
    '"Currency; Not seasonally adjusted","M1; Seasonally adjusted","M2; Seasonally adjusted"\n'
    '"Unit:","Currency","Currency","Currency","Currency","Currency"\n'
    '"Multiplier:","1e+09","1e+09","1e+09","1e+09","1e+09"\n'
    '"Currency:","USD","USD","USD","USD","USD"\n'
    '"Unique Identifier: ","H6/H6_M1/M1_N.M","H6/H6_M2/M2_N.M","H6/H6_M1/MCU_N.M",'
    '"H6/H6_M1/M1.M","H6/H6_M2/M2.M"\n'
)


def _make_fed_h6_csv(data_lines: list[str]) -> str:
    return FED_H6_CSV_HEADER + "Time Period,M1_N.M,M2_N.M,MCU_N.M,M1.M,M2.M\n" + "\n".join(data_lines)


def test_fetch_m2_rows_parses_fed_csv():
    def fetcher(url):
        return _make_fed_h6_csv([
            "2025-01,18000.0,20500.1,28.5,18000.0,20500.1",
            "2025-02,18100.0,20600.5,28.6,18100.0,20600.5",
        ])

    rows = fetch_m2_rows(fetcher=fetcher)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("macro", "M2SL", "money_supply", "2025-01-01", 20500.1, "fed"),
        ("macro", "M2SL", "money_supply", "2025-02-01", 20600.5, "fed"),
    ]


def test_fetch_m2_rows_skips_empty_lines():
    def fetcher(url):
        return _make_fed_h6_csv([
            "2025-01,18000.0,20500.1,28.5,18000.0,20500.1",
            "",
            "2025-03,18200.0,20700.3,28.7,18200.0,20700.3",
        ])

    rows = fetch_m2_rows(fetcher=fetcher)

    assert [row.date for row in rows] == ["2025-01-01", "2025-03-01"]


def test_fetch_m2_rows_raises_on_empty_data():
    def fetcher(url):
        return FED_H6_CSV_HEADER + "Time Period,M1_N.M,M2_N.M,MCU_N.M,M1.M,M2.M\n"

    with pytest.raises(DataSourceError, match="No valid M2 data"):
        fetch_m2_rows(fetcher=fetcher)


def test_fetch_m2_rows_raises_on_missing_m2_column():
    def fetcher(url):
        return (
            '"Series Description","Other Column"\n'
            '"Unit:","Currency"\n'
            '"Multiplier:","1e+09"\n'
            '"Currency:","USD"\n'
            '"Unique Identifier: ","ID"\n'
            "Time Period,Other Column\n"
            "2025-01,100.0\n"
        )

    with pytest.raises(DataSourceError, match="M2.M column not found"):
        fetch_m2_rows(fetcher=fetcher)


def test_fetch_gold_usd_rows_uses_injected_fetcher():
    import json
    calls = []

    def fetcher(url):
        calls.append(url)
        return json.dumps({
            "chart": {
                "result": [{
                    "timestamp": [1744848000, 1744934400],
                    "indicators": {
                        "quote": [{
                            "close": [2400.50, 2420.75],
                        }],
                    },
                }],
            },
        })

    rows = fetch_gold_usd_rows(fetcher=fetcher)

    assert len(calls) == 1
    assert "GC=F" in calls[0]
    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("gold", "XAUUSD", "close", "2025-04-17", 2400.50, "yahoo"),
        ("gold", "XAUUSD", "close", "2025-04-18", 2420.75, "yahoo"),
    ]


def test_fetch_gold_usd_rows_skips_null_closes():
    import json

    def fetcher(url):
        return json.dumps({
            "chart": {
                "result": [{
                    "timestamp": [1744848000, 1744934400],
                    "indicators": {
                        "quote": [{
                            "close": [2400.50, None],
                        }],
                    },
                }],
            },
        })

    rows = fetch_gold_usd_rows(fetcher=fetcher)

    assert len(rows) == 1
    assert rows[0].date == "2025-04-17"


def test_compute_gold_m2_ratio_rows_aligns_by_date():
    gold_rows = [
        DailyMetric("gold", "XAUUSD", "close", "2025-01-02", 2400.0, "akshare"),
        DailyMetric("gold", "XAUUSD", "close", "2025-01-03", 2420.0, "akshare"),
        DailyMetric("gold", "XAUUSD", "close", "2025-02-01", 2500.0, "akshare"),
    ]
    m2_rows = [
        DailyMetric("macro", "M2SL", "money_supply", "2025-01-01", 20500.0, "fed"),
        DailyMetric("macro", "M2SL", "money_supply", "2025-02-01", 21000.0, "fed"),
    ]

    ratios = compute_gold_m2_ratio_rows(gold_rows, m2_rows)

    # M2 in billions: 20500, 21000
    # 2025-01-02: 2400 / 20500 = 0.11707...
    # 2025-01-03: 2420 / 20500 = 0.11805...
    # 2025-02-01: 2500 / 21000 = 0.11905...
    assert len(ratios) == 3
    assert [(row.asset_type, row.code, row.metric, row.date, round(row.value, 4), row.source) for row in ratios] == [
        ("macro", "GOLD_M2", "ratio", "2025-01-02", 0.1171, "fed"),
        ("macro", "GOLD_M2", "ratio", "2025-01-03", 0.1180, "fed"),
        ("macro", "GOLD_M2", "ratio", "2025-02-01", 0.1190, "fed"),
    ]


def test_compute_gold_m2_ratio_rows_skips_gold_dates_before_first_m2():
    gold_rows = [
        DailyMetric("gold", "XAUUSD", "close", "2024-12-31", 2300.0, "akshare"),
        DailyMetric("gold", "XAUUSD", "close", "2025-01-02", 2400.0, "akshare"),
    ]
    m2_rows = [
        DailyMetric("macro", "M2SL", "money_supply", "2025-01-01", 20500.0, "fed"),
    ]

    ratios = compute_gold_m2_ratio_rows(gold_rows, m2_rows)

    assert len(ratios) == 1
    assert ratios[0].date == "2025-01-02"


def test_compute_gold_m2_ratio_rows_handles_unsorted_m2():
    gold_rows = [
        DailyMetric("gold", "XAUUSD", "close", "2025-02-01", 2500.0, "akshare"),
    ]
    m2_rows = [
        DailyMetric("macro", "M2SL", "money_supply", "2025-02-01", 21000.0, "fed"),
        DailyMetric("macro", "M2SL", "money_supply", "2025-01-01", 20500.0, "fed"),
    ]

    ratios = compute_gold_m2_ratio_rows(gold_rows, m2_rows)

    assert len(ratios) == 1
    # Should use the most recent M2 on/before gold date (Feb value, not Jan)
    assert abs(ratios[0].value - 2500.0 / 21000.0) < 0.0001


def test_compute_gold_m2_ratio_rows_raises_on_empty_gold():
    with pytest.raises(DataSourceError, match="No gold USD data"):
        compute_gold_m2_ratio_rows(
            [],
            [DailyMetric("macro", "M2SL", "money_supply", "2025-01-01", 20500.0, "fed")],
        )


def test_compute_gold_m2_ratio_rows_raises_on_empty_m2():
    with pytest.raises(DataSourceError, match="No M2 data"):
        compute_gold_m2_ratio_rows(
            [DailyMetric("gold", "XAUUSD", "close", "2025-01-02", 2400.0, "akshare")],
            [],
        )


def test_compute_gold_m2_ratio_rows_raises_on_no_overlap():
    gold_rows = [
        DailyMetric("gold", "XAUUSD", "close", "2024-12-31", 2300.0, "akshare"),
    ]
    m2_rows = [
        DailyMetric("macro", "M2SL", "money_supply", "2025-01-01", 20500.0, "fed"),
    ]

    with pytest.raises(DataSourceError, match="No overlapping dates"):
        compute_gold_m2_ratio_rows(gold_rows, m2_rows)


def test_fetch_gold_m2_ratio_rows_orchestrates_both_sources(monkeypatch):
    """Verify fetch_gold_m2_ratio_rows fetches both sources and computes ratio."""
    def mock_gold_usd():
        return [DailyMetric("gold", "XAUUSD", "close", "2025-01-02", 2400.0, "akshare")]

    def mock_m2():
        return [DailyMetric("macro", "M2SL", "money_supply", "2025-01-01", 20500.0, "fed")]

    monkeypatch.setattr("finance_cli.sources.fetch_gold_usd_rows", mock_gold_usd)
    monkeypatch.setattr("finance_cli.sources.fetch_m2_rows", mock_m2)

    rows = fetch_gold_m2_ratio_rows()

    assert len(rows) == 1
    assert rows[0].metric == "ratio"
    assert rows[0].code == "GOLD_M2"
    # 2400 / 20500 ≈ 0.1171
    assert abs(rows[0].value - 2400.0 / 20500.0) < 0.001


# --- dividend yield spread compute tests ---


def test_compute_dividend_yield_spread_rows_aligns_by_exact_date():
    div_rows = [
        DailyMetric("index", "H30269", "dividend_yield", "2025-01-02", 4.5, "akshare"),
        DailyMetric("index", "H30269", "dividend_yield", "2025-01-03", 4.6, "akshare"),
        DailyMetric("index", "H30269", "dividend_yield", "2025-02-01", 4.8, "akshare"),
    ]
    cn10y_rows = [
        DailyMetric("bond", "CN10Y", "yield", "2025-01-02", 1.7, "akshare"),
        DailyMetric("bond", "CN10Y", "yield", "2025-01-03", 1.8, "akshare"),
        DailyMetric("bond", "CN10Y", "yield", "2025-02-01", 1.6, "akshare"),
    ]

    spreads = compute_dividend_yield_spread_rows(div_rows, cn10y_rows)

    assert len(spreads) == 3
    assert [(row.asset_type, row.code, row.metric, row.date, round(row.value, 2), row.source) for row in spreads] == [
        ("spread", "H30269", "dividend_yield_spread", "2025-01-02", 2.80, "akshare"),
        ("spread", "H30269", "dividend_yield_spread", "2025-01-03", 2.80, "akshare"),
        ("spread", "H30269", "dividend_yield_spread", "2025-02-01", 3.20, "akshare"),
    ]


def test_compute_dividend_yield_spread_rows_skips_nonmatching_dates():
    div_rows = [
        DailyMetric("index", "H30269", "dividend_yield", "2025-01-01", 4.0, "akshare"),
        DailyMetric("index", "H30269", "dividend_yield", "2025-01-02", 4.5, "akshare"),
        DailyMetric("index", "H30269", "dividend_yield", "2025-01-04", 4.2, "akshare"),
    ]
    cn10y_rows = [
        DailyMetric("bond", "CN10Y", "yield", "2025-01-02", 1.7, "akshare"),
        DailyMetric("bond", "CN10Y", "yield", "2025-01-03", 1.8, "akshare"),
    ]

    spreads = compute_dividend_yield_spread_rows(div_rows, cn10y_rows)

    # Only 2025-01-02 matches; 01-01 (div only), 01-03 (cn10y only), 01-04 (div only) are skipped
    assert len(spreads) == 1
    assert spreads[0].date == "2025-01-02"
    assert abs(spreads[0].value - 2.8) < 0.01


def test_compute_dividend_yield_spread_rows_handles_unsorted_input():
    div_rows = [
        DailyMetric("index", "H30269", "dividend_yield", "2025-02-01", 4.8, "akshare"),
        DailyMetric("index", "H30269", "dividend_yield", "2025-01-02", 4.5, "akshare"),
    ]
    cn10y_rows = [
        DailyMetric("bond", "CN10Y", "yield", "2025-01-02", 1.7, "akshare"),
        DailyMetric("bond", "CN10Y", "yield", "2025-02-01", 1.6, "akshare"),
    ]

    spreads = compute_dividend_yield_spread_rows(div_rows, cn10y_rows)

    assert len(spreads) == 2
    assert spreads[0].date == "2025-01-02"
    assert spreads[1].date == "2025-02-01"


def test_compute_dividend_yield_spread_rows_raises_on_empty_div_yield():
    with pytest.raises(DataSourceError, match="No dividend yield data"):
        compute_dividend_yield_spread_rows(
            [],
            [DailyMetric("bond", "CN10Y", "yield", "2025-01-01", 1.7, "akshare")],
        )


def test_compute_dividend_yield_spread_rows_raises_on_empty_cn10y():
    with pytest.raises(DataSourceError, match="No CN10Y yield data"):
        compute_dividend_yield_spread_rows(
            [DailyMetric("index", "H30269", "dividend_yield", "2025-01-02", 4.5, "akshare")],
            [],
        )


def test_compute_dividend_yield_spread_rows_raises_on_no_overlap():
    div_rows = [
        DailyMetric("index", "H30269", "dividend_yield", "2024-12-31", 4.0, "akshare"),
    ]
    cn10y_rows = [
        DailyMetric("bond", "CN10Y", "yield", "2025-01-01", 1.7, "akshare"),
    ]

    with pytest.raises(DataSourceError, match="No overlapping dates"):
        compute_dividend_yield_spread_rows(div_rows, cn10y_rows)


def test_fetch_dividend_yield_spread_rows_orchestrates_both_sources(monkeypatch):
    """Verify fetch_dividend_yield_spread_rows fetches both sources and computes spread."""

    def mock_div(code):
        return [DailyMetric("index", code, "dividend_yield", "2025-01-02", 4.5, "akshare")]

    def mock_cn10y():
        return [DailyMetric("bond", "CN10Y", "yield", "2025-01-02", 1.7, "akshare")]

    monkeypatch.setattr("finance_cli.sources.fetch_index_dividend_yield_rows", mock_div)
    monkeypatch.setattr("finance_cli.sources.fetch_cn10y_yield_rows", mock_cn10y)

    rows = fetch_dividend_yield_spread_rows("H30269")

    assert len(rows) == 1
    assert rows[0].asset_type == "spread"
    assert rows[0].code == "H30269"
    assert rows[0].metric == "dividend_yield_spread"
    assert abs(rows[0].value - 2.8) < 0.01


# --- ERP compute tests ---


def test_compute_erp_rows_uses_pe_earnings_yield_minus_cn10y():
    pe_rows = [
        DailyMetric("index", "000300", "rolling_pe", "2025-01-02", 20.0, "akshare"),
        DailyMetric("index", "000300", "rolling_pe", "2025-01-03", 25.0, "akshare"),
    ]
    cn10y_rows = [
        DailyMetric("bond", "CN10Y", "yield", "2025-01-02", 2.5, "akshare"),
        DailyMetric("bond", "CN10Y", "yield", "2025-01-03", 2.7, "akshare"),
    ]

    rows = compute_erp_rows(pe_rows, cn10y_rows)

    assert [(row.asset_type, row.code, row.metric, row.date, round(row.value, 2), row.source) for row in rows] == [
        ("spread", "000300", "erp", "2025-01-02", 2.50, "akshare"),
        ("spread", "000300", "erp", "2025-01-03", 1.30, "akshare"),
    ]


def test_compute_erp_rows_skips_nonmatching_dates_and_nonpositive_pe():
    pe_rows = [
        DailyMetric("index", "000300", "rolling_pe", "2025-01-01", 20.0, "akshare"),
        DailyMetric("index", "000300", "rolling_pe", "2025-01-02", 0.0, "akshare"),
        DailyMetric("index", "000300", "rolling_pe", "2025-01-03", -5.0, "akshare"),
        DailyMetric("index", "000300", "rolling_pe", "2025-01-04", 25.0, "akshare"),
    ]
    cn10y_rows = [
        DailyMetric("bond", "CN10Y", "yield", "2025-01-02", 2.5, "akshare"),
        DailyMetric("bond", "CN10Y", "yield", "2025-01-03", 2.6, "akshare"),
        DailyMetric("bond", "CN10Y", "yield", "2025-01-04", 2.7, "akshare"),
    ]

    rows = compute_erp_rows(pe_rows, cn10y_rows)

    assert len(rows) == 1
    assert rows[0].date == "2025-01-04"
    assert abs(rows[0].value - 1.3) < 0.01


def test_compute_erp_rows_raises_on_empty_pe():
    with pytest.raises(DataSourceError, match="No PE data"):
        compute_erp_rows(
            [],
            [DailyMetric("bond", "CN10Y", "yield", "2025-01-01", 2.5, "akshare")],
        )


def test_compute_erp_rows_raises_on_empty_cn10y():
    with pytest.raises(DataSourceError, match="No CN10Y yield data"):
        compute_erp_rows(
            [DailyMetric("index", "000300", "rolling_pe", "2025-01-01", 20.0, "akshare")],
            [],
        )


def test_compute_erp_rows_raises_on_no_overlap():
    with pytest.raises(DataSourceError, match="No overlapping dates"):
        compute_erp_rows(
            [DailyMetric("index", "000300", "rolling_pe", "2025-01-01", 20.0, "akshare")],
            [DailyMetric("bond", "CN10Y", "yield", "2025-01-02", 2.5, "akshare")],
        )


def test_fetch_erp_rows_orchestrates_pe_and_cn10y(monkeypatch):
    def mock_pe(code):
        return [DailyMetric("index", code, "rolling_pe", "2025-01-02", 20.0, "akshare")]

    def mock_cn10y():
        return [DailyMetric("bond", "CN10Y", "yield", "2025-01-02", 2.5, "akshare")]

    monkeypatch.setattr("finance_cli.sources.fetch_index_pe_rows", mock_pe)
    monkeypatch.setattr("finance_cli.sources.fetch_cn10y_yield_rows", mock_cn10y)

    rows = fetch_erp_rows("000300")

    assert len(rows) == 1
    assert rows[0].asset_type == "spread"
    assert rows[0].code == "000300"
    assert rows[0].metric == "erp"
    assert abs(rows[0].value - 2.5) < 0.01
