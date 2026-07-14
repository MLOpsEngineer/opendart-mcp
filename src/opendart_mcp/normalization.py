"""Validation and compact response shaping for the public MCP surface."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Any

SERVICE_NAME = "OpenDART (전자공시시스템 DART)"
REPORT_CODES = {"11011", "11012", "11013", "11014"}
STATEMENT_TYPES = {"BS", "IS", "CIS", "CF", "SCE"}
FS_DIVISIONS = {"CFS", "OFS"}
_CORP_CODE = re.compile(r"^[0-9]{8}$")
_YEAR = re.compile(r"^[0-9]{4}$")
_DATE = re.compile(r"^[0-9]{8}$")


def validate_corp_code(value: str) -> str:
    value = value.strip()
    if not _CORP_CODE.fullmatch(value):
        raise ValueError("corp_code must contain exactly 8 digits")
    return value


def validate_business_year(value: str) -> str:
    value = value.strip()
    if not _YEAR.fullmatch(value) or not 2015 <= int(value) <= date.today().year:
        raise ValueError(f"business_year must be between 2015 and {date.today().year}")
    return value


def validate_report_code(value: str) -> str:
    if value not in REPORT_CODES:
        raise ValueError("report_code must be one of 11011, 11012, 11013, or 11014")
    return value


def validate_statement_type(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    if normalized not in STATEMENT_TYPES:
        raise ValueError("statement_type must be BS, IS, CIS, CF, or SCE")
    return normalized


def validate_fs_division(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in FS_DIVISIONS:
        raise ValueError("fs_division must be CFS or OFS")
    return normalized


def validate_date_range(begin_date: str, end_date: str) -> tuple[str, str]:
    if not _DATE.fullmatch(begin_date) or not _DATE.fullmatch(end_date):
        raise ValueError("dates must use YYYYMMDD format")
    try:
        begin = datetime.strptime(begin_date, "%Y%m%d").date()
        end = datetime.strptime(end_date, "%Y%m%d").date()
    except ValueError as exc:
        raise ValueError("dates must be valid calendar dates") from exc
    if begin > end:
        raise ValueError("begin_date must not be after end_date")
    if (end - begin).days > 366:
        raise ValueError("date range must not exceed 366 days")
    return begin_date, end_date


def to_number(value: Any) -> int | float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text in {"-", "--"}:
        return None
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return None


def rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    value = payload.get("list", [])
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def compact(value: Any, limit: int = 240) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text[:limit] or None


def result(endpoint: str, data: Any, *, count: int | None = None) -> dict[str, Any]:
    response: dict[str, Any] = {
        "status": "ok",
        "source": {
            "service": SERVICE_NAME,
            "endpoint": endpoint,
            "retrieved_at": datetime.now(UTC).isoformat(),
        },
        "data": data,
    }
    if count is not None:
        response["count"] = count
    return response


def company_profile(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "corp_code": compact(payload.get("corp_code")),
        "company_name": compact(payload.get("corp_name")),
        "company_name_english": compact(payload.get("corp_name_eng")),
        "stock_name": compact(payload.get("stock_name")),
        "stock_code": compact(payload.get("stock_code")),
        "market": compact(payload.get("corp_cls")),
        "ceo": compact(payload.get("ceo_nm")),
        "business_number": compact(payload.get("bizr_no")),
        "industry_code": compact(payload.get("induty_code")),
        "established_on": compact(payload.get("est_dt")),
        "fiscal_month": compact(payload.get("acc_mt")),
        "website": compact(payload.get("hm_url")),
        "address": compact(payload.get("adres")),
    }


def disclosures(payload: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    return [
        {
            "receipt_number": compact(item.get("rcept_no")),
            "received_on": compact(item.get("rcept_dt")),
            "company_name": compact(item.get("corp_name")),
            "company_code": compact(item.get("corp_code")),
            "market": compact(item.get("corp_cls")),
            "report_name": compact(item.get("report_nm")),
            "filer_name": compact(item.get("flr_nm")),
            "note": compact(item.get("rm")),
        }
        for item in rows(payload)[:limit]
    ]


def financial_accounts(
    payload: dict[str, Any], limit: int, statement_type: str | None
) -> list[dict[str, Any]]:
    filtered = rows(payload)
    if statement_type:
        filtered = [item for item in filtered if item.get("sj_div") == statement_type]
    return [
        {
            "statement_type": compact(item.get("sj_div")),
            "statement_name": compact(item.get("sj_nm")),
            "account_id": compact(item.get("account_id")),
            "account_name": compact(item.get("account_nm")),
            "current_period_name": compact(item.get("thstrm_nm")),
            "current_amount": to_number(item.get("thstrm_amount")),
            "current_cumulative_amount": to_number(item.get("thstrm_add_amount")),
            "prior_period_name": compact(item.get("frmtrm_nm")),
            "prior_amount": to_number(item.get("frmtrm_amount")),
            "currency": compact(item.get("currency")),
        }
        for item in filtered[:limit]
    ]


def dividend_rows(payload: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    return [
        {
            "category": compact(item.get("se")),
            "stock_type": compact(item.get("stock_knd")),
            "current_period": compact(item.get("thstrm")),
            "prior_period": compact(item.get("frmtrm")),
            "two_periods_prior": compact(item.get("lwfr")),
            "settlement_date": compact(item.get("stlm_dt")),
        }
        for item in rows(payload)[:limit]
    ]


def shareholder_rows(payload: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    return [
        {
            "name": compact(item.get("nm")),
            "relationship": compact(item.get("relate")),
            "stock_type": compact(item.get("stock_knd")),
            "beginning_shares": to_number(item.get("bsis_posesn_stock_co")),
            "beginning_ownership_percent": to_number(item.get("bsis_posesn_stock_qota_rt")),
            "ending_shares": to_number(item.get("trmend_posesn_stock_co")),
            "ending_ownership_percent": to_number(item.get("trmend_posesn_stock_qota_rt")),
            "settlement_date": compact(item.get("stlm_dt")),
        }
        for item in rows(payload)[:limit]
    ]


def employee_rows(payload: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    return [
        {
            "business_segment": compact(item.get("fo_bbm")),
            "gender": compact(item.get("sexdstn")),
            "regular_employees": to_number(item.get("rgllbr_co")),
            "contract_employees": to_number(item.get("cnttk_co")),
            "total_employees": to_number(item.get("sm")),
            "average_tenure": compact(item.get("avrg_cnwk_sdytrn")),
            "annual_payroll": to_number(item.get("fyer_salary_totamt")),
            "average_salary": to_number(item.get("jan_salary_am")),
            "settlement_date": compact(item.get("stlm_dt")),
        }
        for item in rows(payload)[:limit]
    ]
