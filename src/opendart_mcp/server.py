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
from .routing import classify_disclosure_request as classify_request
from .specialists import (
    SPECIALIST_TOOLS,
    SpecialistServerRegistry,
    list_specialists,
    select_specialist_tool,
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
    version="1.1.0",
    stateless_http=True,
)
client = OpenDartClient()
specialist_registry = SpecialistServerRegistry(client)


def annotations(title: str) -> ToolAnnotations:
    return ToolAnnotations(title=title, **READ_ONLY)


def _build_public_specialist_handler(server_id: str, tool_name: str):
    """Bind a specialist identity once so every public MCP tool dispatches correctly."""

    async def invoke(
        arguments: Annotated[
            dict[str, Any],
            Field(
                description=(
                    "Arguments accepted by this OpenDART endpoint. Depending on the tool, use "
                    "corp_code or corp_name, business_year, report_code, begin_date, end_date, "
                    "receipt_number, corp_codes, fs_division, statement_type, index_code, and "
                    "max_items."
                )
            ),
        ],
    ) -> dict[str, Any]:
        return await specialist_registry.call_tool(server_id, tool_name, arguments)

    return invoke


def _register_public_specialist_tools() -> None:
    """Expose every original specialist adapter in the top-level MCP tool catalog."""

    registered_names: set[str] = set()
    for server_id, specs in SPECIALIST_TOOLS.items():
        for spec in specs:
            if spec.name in registered_names:
                raise RuntimeError(f"duplicate public specialist tool name: {spec.name}")
            registered_names.add(spec.name)
            mcp.tool(
                name=spec.name,
                title=f"{server_id}: {spec.label}",
                description=(
                    f"Use {SERVICE_DESCRIPTION} to retrieve {spec.label} through the "
                    f"{server_id} disclosure domain. This read-only specialist tool calls "
                    f"OpenDART endpoint {spec.endpoint}."
                ),
                annotations=annotations(f"{server_id}: {spec.label}"),
                tags={"opendart", "specialist", server_id},
            )(_build_public_specialist_handler(server_id, spec.name))


@mcp.custom_route("/health", methods=["GET"])
async def health_check(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "opendart-mcp", "version": "1.1.0"})


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
    name="classify_disclosure_request",
    description=(
        "Use Disclosure Compass(공시나침반) to classify a natural-language request into "
        "sixteen OpenDART (전자공시시스템 DART) disclosure domains and inspect the "
        "available specialist-server tools."
    ),
    annotations=annotations("Classify disclosure request"),
)
async def classify_disclosure_request(
    query: Annotated[
        str,
        Field(min_length=1, max_length=500, description="Korean disclosure-related request"),
    ],
    top_k: Annotated[
        int,
        Field(ge=1, le=16, description="Number of ranked disclosure domains to return"),
    ] = 3,
) -> dict[str, Any]:
    return classify_request(query, top_k)


@mcp.tool(
    name="list_disclosure_servers",
    description=(
        "Use Disclosure Compass(공시나침반) to list the sixteen in-process specialist "
        "MCP servers and their original OpenDART (전자공시시스템 DART) tool names and "
        "endpoints. Optionally inspect one server."
    ),
    annotations=annotations("List disclosure specialist servers"),
)
async def list_disclosure_servers(
    server_id: Annotated[
        str | None,
        Field(description="Optional canonical specialist server ID"),
    ] = None,
) -> dict[str, Any]:
    return list_specialists(server_id)


@mcp.tool(
    name="call_disclosure_server_tool",
    description=(
        "Use Disclosure Compass(공시나침반) to call one named OpenDART "
        "(전자공시시스템 DART) tool on one of the sixteen in-process specialist MCP "
        "servers. Use list_disclosure_servers first when the server or tool is unknown."
    ),
    annotations=annotations("Call disclosure specialist tool"),
)
async def call_disclosure_server_tool(
    server_id: Annotated[str, Field(description="Canonical specialist server ID")],
    tool_name: Annotated[str, Field(description="Original specialist MCP tool name")],
    arguments: Annotated[
        dict[str, Any],
        Field(
            description=(
                "Tool arguments such as corp_code/corp_name, business_year/report_code, "
                "begin_date/end_date, receipt_number, and max_items"
            )
        ),
    ],
) -> dict[str, Any]:
    return await specialist_registry.call_tool(server_id, tool_name, arguments)


@mcp.tool(
    name="route_and_call_disclosure",
    description=(
        "Use Disclosure Compass(공시나침반) to classify a Korean disclosure request, "
        "select one of sixteen specialist MCP servers and one of its tools, then execute "
        "the selected OpenDART (전자공시시스템 DART) tool in one call."
    ),
    annotations=annotations("Route and call disclosure specialist"),
)
async def route_and_call_disclosure(
    query: Annotated[
        str,
        Field(min_length=1, max_length=500, description="Korean disclosure-related request"),
    ],
    corp_code: Annotated[
        str | None,
        Field(description="Optional eight-digit OpenDART company code"),
    ] = None,
    corp_name: Annotated[
        str | None,
        Field(description="Optional company or stock name resolved through OpenDART"),
    ] = None,
    tool_name: Annotated[
        str | None,
        Field(description="Optional exact inner tool name; otherwise selected from query"),
    ] = None,
    business_year: Annotated[
        str | None,
        Field(description="Optional business year; defaults to the previous year"),
    ] = None,
    report_code: Annotated[
        str,
        Field(description="11011 annual, 11012 half, 11013 Q1, or 11014 Q3"),
    ] = "11011",
    begin_date: Annotated[
        str | None,
        Field(description="Optional start date in YYYYMMDD; defaults to one year ago"),
    ] = None,
    end_date: Annotated[
        str | None,
        Field(description="Optional end date in YYYYMMDD; defaults to today"),
    ] = None,
    max_items: Annotated[int, Field(ge=1, le=50)] = 20,
    corp_codes: Annotated[
        list[str] | None,
        Field(description="Optional list of up to ten company codes for comparison tools"),
    ] = None,
    receipt_number: Annotated[
        str | None,
        Field(description="Optional 14-digit filing receipt number for document/XBRL tools"),
    ] = None,
    fs_division: Annotated[
        str | None,
        Field(description="Optional CFS consolidated or OFS separate statement basis"),
    ] = None,
    statement_type: Annotated[
        str | None,
        Field(description="Optional XBRL taxonomy statement code such as BS1 or IS1"),
    ] = None,
    index_code: Annotated[
        str | None,
        Field(description="Optional OpenDART financial index classification code"),
    ] = None,
    disclosure_type: Annotated[
        str | None,
        Field(description="Optional OpenDART disclosure type filter for dart_list"),
    ] = None,
) -> dict[str, Any]:
    routed = classify_request(query, 1)
    route = routed["routes"][0]
    server_id = route["category"]
    selected = select_specialist_tool(server_id, query)
    if tool_name is not None:
        available = {tool.name for tool in SPECIALIST_TOOLS[server_id]}
        if tool_name not in available:
            raise ValueError(f"unknown tool '{tool_name}' for server '{server_id}'")
        selected = next(tool for tool in SPECIALIST_TOOLS[server_id] if tool.name == tool_name)
    arguments = {
        key: value
        for key, value in {
            "corp_code": corp_code,
            "corp_name": corp_name,
            "business_year": business_year,
            "report_code": report_code,
            "begin_date": begin_date,
            "end_date": end_date,
            "max_items": max_items,
            "corp_codes": corp_codes,
            "receipt_number": receipt_number,
            "fs_division": fs_division,
            "statement_type": statement_type,
            "index_code": index_code,
            "disclosure_type": disclosure_type,
        }.items()
        if value is not None
    }
    called = await specialist_registry.call_tool(server_id, selected.name, arguments)
    return {
        "query": query,
        "route": route,
        "selected_server": server_id,
        "selected_tool": selected.name,
        "result": called,
    }


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


_register_public_specialist_tools()


app = mcp.http_app(path="/mcp")


def main() -> None:
    port = int(os.getenv("PORT", "8000"))
    mcp.run(transport="http", host="0.0.0.0", port=port, path="/mcp", stateless_http=True)


if __name__ == "__main__":
    main()
