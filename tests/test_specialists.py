from __future__ import annotations

from typing import Any

import pytest

from opendart_mcp.specialists import (
    SPECIALIST_TOOLS,
    SpecialistServerRegistry,
    SpecialistTool,
    list_specialists,
    select_specialist_tool,
    specialist_tool_count,
)

REPRESENTATIVE_TOOLS = {
    "disclosure_search": ("dart_company", "company.json"),
    "shareholder_stock": ("dart_alotMatter", "alotMatter.json"),
    "executive_compensation": ("dart_empSttus", "empSttus.json"),
    "debt_securities": ("dart_cprndNrdmpBlce", "cprndNrdmpBlce.json"),
    "audit_fund": ("dart_accnutAdtorNmNdAdtOpinion", "accnutAdtorNmNdAdtOpinion.json"),
    "financial_statement": ("dart_fnlttSinglAcntAll", "fnlttSinglAcntAll.json"),
    "equity_disclosure": ("dart_majorstock", "majorstock.json"),
    "securities_registration": ("dart_estkRs", "estkRs.json"),
    "capital_change": ("dart_piicDecsn", "piicDecsn.json"),
    "treasury_stock": ("dart_tsstkAqDecsn", "tsstkAqDecsn.json"),
    "convertible_securities": ("dart_cvbdIsDecsn", "cvbdIsDecsn.json"),
    "merger_division": ("dart_cmpMgDecsn", "cmpMgDecsn.json"),
    "business_transfer": ("dart_bsnInhDecsn", "bsnInhDecsn.json"),
    "overseas_listing": ("dart_ovLstDecsn", "ovLstDecsn.json"),
    "equity_investment": ("dart_otcprStkInvscr", "otcprStkInvscr.json"),
    "corporate_issues": ("dart_dfOcr", "dfOcr.json"),
}

ALL_SPECIALIST_TOOL_CASES = [
    (server_id, tool) for server_id, tools in SPECIALIST_TOOLS.items() for tool in tools
]


class FakeOpenDartClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def get_json(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((endpoint, params))
        return {
            "status": "000",
            "message": "OK",
            "list": [{"endpoint": endpoint, "corp_code": params.get("corp_code")}],
        }

    async def resolve_corp_code(self, corp_name: str) -> str:
        assert corp_name == "삼성전자"
        return "00126380"

    async def search_corp_codes(self, corp_name: str, max_items: int) -> list[dict[str, str]]:
        return [{"corp_code": "00126380", "corp_name": corp_name, "stock_code": "005930"}][
            :max_items
        ]

    async def get_binary_metadata(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((endpoint, params))
        return {"content_type": "application/zip", "content_length": 123, "files": []}


def test_registry_contains_all_original_servers_and_tools() -> None:
    catalog = list_specialists()

    assert len(SPECIALIST_TOOLS) == 16
    assert specialist_tool_count() == 82
    assert catalog["server_count"] == 16
    assert catalog["tool_count"] == 82
    assert {server["server_id"] for server in catalog["servers"]} == set(REPRESENTATIVE_TOOLS)


@pytest.mark.asyncio
async def test_every_specialist_server_registers_its_complete_tool_set() -> None:
    registry = SpecialistServerRegistry(FakeOpenDartClient())  # type: ignore[arg-type]

    for server_id, expected_specs in SPECIALIST_TOOLS.items():
        assert set(await registry.list_tools(server_id)) == {tool.name for tool in expected_specs}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("server_id", "tool_name", "endpoint"),
    [
        (server_id, tool_name, endpoint)
        for server_id, (tool_name, endpoint) in REPRESENTATIVE_TOOLS.items()
    ],
)
async def test_each_specialist_server_executes_a_tool_through_fastmcp(
    server_id: str, tool_name: str, endpoint: str
) -> None:
    fake = FakeOpenDartClient()
    registry = SpecialistServerRegistry(fake)  # type: ignore[arg-type]

    result = await registry.call_tool(
        server_id,
        tool_name,
        {
            "corp_code": "00126380",
            "business_year": "2024",
            "report_code": "11011",
            "begin_date": "20250101",
            "end_date": "20251231",
            "max_items": 5,
        },
    )

    assert result["status"] == "ok"
    assert result["server_id"] == server_id
    assert result["tool_name"] == tool_name
    assert result["endpoint"] == endpoint
    assert fake.calls[-1][0] == endpoint


def arguments_for(tool: SpecialistTool) -> dict[str, Any]:
    common = {
        "corp_code": "00126380",
        "business_year": "2024",
        "report_code": "11011",
        "begin_date": "20250101",
        "end_date": "20251231",
        "max_items": 5,
    }
    if tool.kind in {"statement_multi", "index_multi"}:
        common["corp_codes"] = ["00126380", "00164742"]
    if tool.kind in {"document", "xbrl"}:
        common["receipt_number"] = "20250101000001"
    if tool.kind == "taxonomy":
        common["statement_type"] = "BS1"
    if tool.kind == "corp_codes":
        common["corp_name"] = "삼성전자"
    return common


@pytest.mark.asyncio
@pytest.mark.parametrize(("server_id", "tool"), ALL_SPECIALIST_TOOL_CASES)
async def test_all_eighty_two_tools_execute_their_registered_adapter(
    server_id: str, tool: SpecialistTool
) -> None:
    fake = FakeOpenDartClient()
    registry = SpecialistServerRegistry(fake)  # type: ignore[arg-type]

    result = await registry.call_tool(server_id, tool.name, arguments_for(tool))

    assert result["status"] == "ok"
    assert result["server_id"] == server_id
    assert result["tool_name"] == tool.name
    assert result["endpoint"] == tool.endpoint


def test_keyword_selector_chooses_specific_tool_inside_routed_server() -> None:
    assert (
        select_specialist_tool("convertible_securities", "삼성전자 전환사채 발행 결정").name
        == "dart_cvbdIsDecsn"
    )
    assert select_specialist_tool("corporate_issues", "최근 부도 발생 공시").name == "dart_dfOcr"


@pytest.mark.asyncio
async def test_registry_resolves_company_name_before_calling_tool() -> None:
    fake = FakeOpenDartClient()
    registry = SpecialistServerRegistry(fake)  # type: ignore[arg-type]

    result = await registry.call_tool(
        "equity_disclosure",
        "dart_majorstock",
        {"corp_name": "삼성전자"},
    )

    assert result["data"][0]["corp_code"] == "00126380"


@pytest.mark.asyncio
async def test_registry_can_proxy_a_specialist_tool_to_a_compatible_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeOpenDartClient()
    registry = SpecialistServerRegistry(  # type: ignore[arg-type]
        fake,
        upstream_gateway_url="https://gateway.example/mcp",
    )
    calls: list[tuple[str, str, dict[str, Any]]] = []

    async def call_upstream(
        server_id: str, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        calls.append((server_id, tool_name, arguments))
        return {"status": "ok", "proxied": True}

    monkeypatch.setattr(registry, "_call_upstream", call_upstream)

    result = await registry.call_tool(
        "disclosure_search",
        "dart_company",
        {"corp_code": "00126380"},
    )

    assert result == {"status": "ok", "proxied": True}
    assert calls == [("disclosure_search", "dart_company", {"corp_code": "00126380"})]
    assert fake.calls == []


@pytest.mark.asyncio
async def test_registry_rejects_unknown_server_and_tool() -> None:
    registry = SpecialistServerRegistry(FakeOpenDartClient())  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="unknown disclosure server"):
        await registry.call_tool("missing", "dart_list", {})
    with pytest.raises(ValueError, match="unknown tool"):
        await registry.call_tool("disclosure_search", "missing", {})
