import pandas as pd

from finance_cli.sources import normalize_gold_rows, normalize_index_pe_rows


def test_normalize_index_pe_rows_accepts_common_akshare_columns():
    frame = pd.DataFrame(
        {
            "日期": ["2026-04-17", "2026-04-20"],
            "滚动市盈率": [12.3, 12.8],
        }
    )

    rows = normalize_index_pe_rows("000300", frame)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value) for row in rows] == [
        ("index", "000300", "pe_ttm", "2026-04-17", 12.3),
        ("index", "000300", "pe_ttm", "2026-04-20", 12.8),
    ]


def test_normalize_gold_rows_accepts_common_akshare_columns():
    frame = pd.DataFrame(
        {
            "日期": ["2026-04-17", "2026-04-20"],
            "收盘价": [530.5, 535.2],
        }
    )

    rows = normalize_gold_rows(frame)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value) for row in rows] == [
        ("gold", "AU9999", "close", "2026-04-17", 530.5),
        ("gold", "AU9999", "close", "2026-04-20", 535.2),
    ]
