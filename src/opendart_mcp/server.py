"""Stateless Streamable HTTP MCP surface for OpenDART."""

from __future__ import annotations

import os
from typing import Annotated, Any

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse

from .client import OpenDartClient
from .normalization import (
    company_profile,
    disclosures,
    dividend_rows,
    employee_rows,
    financial_accounts,
    result,
    shareholder_rows,
    validate_business_year,
    validate_corp_code,
    validate_date_range,
    validate_fs_division,
    validate_report_code,
    validate_statement_type,
)

SERVICE_DESCRIPTION = "Disclosure Compass(공시나침반) with OpenDART (전자공시시스템 DART)"
READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "openWorldHint": True,
    "idempotentHint": True,
}

mcp = FastMCP(
    "Disclosure Compass(공시나침반)",
    instructions=(
        "Use these read-only tools to retrieve concise Korean corporate disclosure data "
        f"from {SERVICE_DESCRIPTION}. Company identifiers are eight-digit OpenDART corp codes."
    ),
    version="1.0.0",
    stateless_http=True,
)
client = OpenDartClient()


def annotations(title: str) -> ToolAnnotations:
    return ToolAnnotations(title=title, **READ_ONLY)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "opendart-mcp", "version": "1.0.0"})


@mcp.tool(
    name="get_company_profile",
    description=(
        "Use Disclosure Compass(공시나침반) to get a company's basic profile and listing "
        "details from OpenDART (전자공시시스템 DART) using its eight-digit corp code."
    ),
    annotations=annotations("Get company profile"),
)
async def get_company_profile(
    corp_code: Annotated[str, Field(description="Eight-digit OpenDART company code")],
) -> dict[str, Any]:
    corp_code = validate_corp_code(corp_code)
    payload = await client.get_json("company.json", {"corp_code": corp_code})
    return result("company.json", company_profile(payload))


@mcp.tool(
    name="search_disclosures",
    description=(
        "Use Disclosure Compass(공시나침반) to search public filings from "
        "OpenDART (전자공시시스템 DART) within a bounded date range, optionally "
        "restricted to one eight-digit corp code."
    ),
    annotations=annotations("Search disclosures"),
)
async def search_disclosures(
    begin_date: Annotated[str, Field(description="Start date in YYYYMMDD format")],
    end_date: Annotated[str, Field(description="End date in YYYYMMDD format")],
    corp_code: Annotated[
        str | None,
        Field(description="Optional eight-digit OpenDART company code"),
    ] = None,
    max_items: Annotated[int, Field(ge=1, le=20, description="Maximum result rows")] = 10,
) -> dict[str, Any]:
    begin_date, end_date = validate_date_range(begin_date, end_date)
    if corp_code is not None:
        corp_code = validate_corp_code(corp_code)
    payload = await client.get_json(
        "list.json",
        {
            "bgn_de": begin_date,
            "end_de": end_date,
            "corp_code": corp_code,
            "page_no": 1,
            "page_count": max_items,
            "sort": "date",
            "sort_mth": "desc",
        },
    )
    items = disclosures(payload, max_items)
    return result("list.json", items, count=len(items))


@mcp.tool(
    name="get_financial_statement",
    description=(
        "Use Disclosure Compass(공시나침반) to get normalized financial statement "
        "accounts from OpenDART (전자공시시스템 DART) for one company, year, report, "
        "and consolidated or separate basis."
    ),
    annotations=annotations("Get financial statement"),
)
async def get_financial_statement(
    corp_code: Annotated[str, Field(description="Eight-digit OpenDART company code")],
    business_year: Annotated[str, Field(description="Business year from 2015 onward")],
    report_code: Annotated[
        str,
        Field(description="11011 annual, 11012 half, 11013 Q1, or 11014 Q3"),
    ] = "11011",
    fs_division: Annotated[
        str,
        Field(description="CFS for consolidated or OFS for separate statements"),
    ] = "CFS",
    statement_type: Annotated[
        str | None,
        Field(description="Optional BS, IS, CIS, CF, or SCE filter"),
    ] = None,
    max_items: Annotated[int, Field(ge=1, le=50, description="Maximum account rows")] = 30,
) -> dict[str, Any]:
    corp_code = validate_corp_code(corp_code)
    business_year = validate_business_year(business_year)
    report_code = validate_report_code(report_code)
    fs_division = validate_fs_division(fs_division)
    statement_type = validate_statement_type(statement_type)
    payload = await client.get_json(
        "fnlttSinglAcntAll.json",
        {
            "corp_code": corp_code,
            "bsns_year": business_year,
            "reprt_code": report_code,
            "fs_div": fs_division,
        },
    )
    items = financial_accounts(payload, max_items, statement_type)
    return result("fnlttSinglAcntAll.json", items, count=len(items))


async def _periodic_rows(
    endpoint: str,
    corp_code: str,
    business_year: str,
    report_code: str,
) -> dict[str, Any]:
    return await client.get_json(
        endpoint,
        {
            "corp_code": validate_corp_code(corp_code),
            "bsns_year": validate_business_year(business_year),
            "reprt_code": validate_report_code(report_code),
        },
    )


@mcp.tool(
    name="get_dividend_information",
    description=(
        "Use Disclosure Compass(공시나침반) to get dividend-related rows from "
        "OpenDART (전자공시시스템 DART) for one company and reporting period."
    ),
    annotations=annotations("Get dividend information"),
)
async def get_dividend_information(
    corp_code: Annotated[str, Field(description="Eight-digit OpenDART company code")],
    business_year: Annotated[str, Field(description="Business year from 2015 onward")],
    report_code: Annotated[
        str,
        Field(description="11011 annual, 11012 half, 11013 Q1, or 11014 Q3"),
    ] = "11011",
    max_items: Annotated[int, Field(ge=1, le=50, description="Maximum result rows")] = 30,
) -> dict[str, Any]:
    payload = await _periodic_rows("alotMatter.json", corp_code, business_year, report_code)
    items = dividend_rows(payload, max_items)
    return result("alotMatter.json", items, count=len(items))


@mcp.tool(
    name="get_major_shareholders",
    description=(
        "Use Disclosure Compass(공시나침반) to get major shareholder positions from "
        "OpenDART (전자공시시스템 DART) for one company and reporting period."
    ),
    annotations=annotations("Get major shareholders"),
)
async def get_major_shareholders(
    corp_code: Annotated[str, Field(description="Eight-digit OpenDART company code")],
    business_year: Annotated[str, Field(description="Business year from 2015 onward")],
    report_code: Annotated[
        str,
        Field(description="11011 annual, 11012 half, 11013 Q1, or 11014 Q3"),
    ] = "11011",
    max_items: Annotated[int, Field(ge=1, le=50, description="Maximum result rows")] = 30,
) -> dict[str, Any]:
    payload = await _periodic_rows("hyslrSttus.json", corp_code, business_year, report_code)
    items = shareholder_rows(payload, max_items)
    return result("hyslrSttus.json", items, count=len(items))


@mcp.tool(
    name="get_employee_statistics",
    description=(
        "Use Disclosure Compass(공시나침반) to get employee counts, tenure, and pay "
        "statistics from OpenDART (전자공시시스템 DART) for one company and reporting period."
    ),
    annotations=annotations("Get employee statistics"),
)
async def get_employee_statistics(
    corp_code: Annotated[str, Field(description="Eight-digit OpenDART company code")],
    business_year: Annotated[str, Field(description="Business year from 2015 onward")],
    report_code: Annotated[
        str,
        Field(description="11011 annual, 11012 half, 11013 Q1, or 11014 Q3"),
    ] = "11011",
    max_items: Annotated[int, Field(ge=1, le=50, description="Maximum result rows")] = 30,
) -> dict[str, Any]:
    payload = await _periodic_rows("empSttus.json", corp_code, business_year, report_code)
    items = employee_rows(payload, max_items)
    return result("empSttus.json", items, count=len(items))


app = mcp.http_app(path="/mcp")


def main() -> None:
    port = int(os.getenv("PORT", "8000"))
    mcp.run(transport="http", host="0.0.0.0", port=port, path="/mcp", stateless_http=True)


if __name__ == "__main__":
    main()
