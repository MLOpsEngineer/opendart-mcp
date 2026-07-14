from __future__ import annotations

import pytest

from opendart_mcp.normalization import (
    disclosures,
    financial_accounts,
    shareholder_rows,
    validate_corp_code,
    validate_date_range,
)


def test_validation_rejects_invalid_company_and_large_date_range() -> None:
    with pytest.raises(ValueError, match="8 digits"):
        validate_corp_code("005930")
    with pytest.raises(ValueError, match="366 days"):
        validate_date_range("20240101", "20250102")


def test_disclosures_are_limited_and_drop_unknown_fields() -> None:
    payload = {
        "list": [
            {
                "rcept_no": "20260101000001",
                "rcept_dt": "20260101",
                "corp_name": "Example Corp",
                "corp_code": "00123456",
                "corp_cls": "Y",
                "report_nm": "Annual report",
                "flr_nm": "Example Corp",
                "secret_internal_field": "must not leak",
            },
            {"rcept_no": "20260101000002", "corp_name": "Second Corp"},
        ]
    }

    shaped = disclosures(payload, 1)

    assert len(shaped) == 1
    assert shaped[0]["receipt_number"] == "20260101000001"
    assert "secret_internal_field" not in shaped[0]


def test_financial_rows_filter_and_convert_amounts() -> None:
    payload = {
        "list": [
            {
                "sj_div": "BS",
                "sj_nm": "Balance sheet",
                "account_nm": "Assets",
                "thstrm_amount": "1,234",
                "frmtrm_amount": "-",
                "currency": "KRW",
            },
            {"sj_div": "IS", "account_nm": "Revenue", "thstrm_amount": "500"},
        ]
    }

    shaped = financial_accounts(payload, 10, "BS")

    assert shaped == [
        {
            "statement_type": "BS",
            "statement_name": "Balance sheet",
            "account_id": None,
            "account_name": "Assets",
            "current_period_name": None,
            "current_amount": 1234,
            "current_cumulative_amount": None,
            "prior_period_name": None,
            "prior_amount": None,
            "currency": "KRW",
        }
    ]


def test_shareholder_rows_convert_percentages() -> None:
    payload = {
        "list": [
            {
                "nm": "Holder",
                "trmend_posesn_stock_co": "10,000",
                "trmend_posesn_stock_qota_rt": "12.5",
            }
        ]
    }

    shaped = shareholder_rows(payload, 10)

    assert shaped[0]["ending_shares"] == 10_000
    assert shaped[0]["ending_ownership_percent"] == 12.5
