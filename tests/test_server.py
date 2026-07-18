from __future__ import annotations

import re

import pytest
from fastmcp import Client
from starlette.testclient import TestClient

import opendart_mcp.server as server_module
from opendart_mcp.server import app, mcp
from opendart_mcp.specialists import SPECIALIST_TOOLS, specialist_tool_count


@pytest.mark.asyncio
async def test_mcp_exposes_gateway_and_all_specialist_tools_with_complete_annotations() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()

    gateway_tool_names = {
        "get_company_profile",
        "search_disclosures",
        "get_financial_statement",
        "get_dividend_information",
        "get_major_shareholders",
        "get_employee_statistics",
        "classify_disclosure_request",
        "list_disclosure_servers",
        "call_disclosure_server_tool",
        "route_and_call_disclosure",
    }
    specialist_tool_names = {
        spec.name for specs in SPECIALIST_TOOLS.values() for spec in specs
    }
    assert len(specialist_tool_names) == specialist_tool_count() == 82
    assert len(tools) == len(gateway_tool_names) + specialist_tool_count() == 92
    assert {tool.name for tool in tools} == gateway_tool_names | specialist_tool_names
    for tool in tools:
        assert re.fullmatch(r"[A-Za-z0-9_-]+", tool.name)
        assert "Disclosure Compass(공시나침반)" in (tool.description or "")
        assert "OpenDART (전자공시시스템 DART)" in (tool.description or "")
        assert tool.annotations is not None
        assert tool.annotations.title
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False
        assert tool.annotations.openWorldHint is True
        assert tool.annotations.idempotentHint is True


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "opendart-mcp",
        "version": "1.1.0",
    }


@pytest.mark.asyncio
async def test_route_and_call_executes_selected_specialist_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, dict[str, object]]] = []

    class StubRegistry:
        async def call_tool(
            self, server_id: str, tool_name: str, arguments: dict[str, object]
        ) -> dict[str, object]:
            calls.append((server_id, tool_name, arguments))
            return {"status": "ok", "endpoint": "cvbdIsDecsn.json"}

    monkeypatch.setattr(server_module, "specialist_registry", StubRegistry())

    async with Client(mcp) as client:
        result = await client.call_tool(
            "route_and_call_disclosure",
            {
                "query": "전환사채 발행 결정을 찾아줘",
                "corp_code": "00126380",
                "begin_date": "20250101",
                "end_date": "20251231",
                "receipt_number": "20250101000001",
            },
        )

    assert result.data["selected_server"] == "convertible_securities"
    assert result.data["selected_tool"] == "dart_cvbdIsDecsn"
    assert calls == [
        (
            "convertible_securities",
            "dart_cvbdIsDecsn",
            {
                "corp_code": "00126380",
                "report_code": "11011",
                "begin_date": "20250101",
                "end_date": "20251231",
                "max_items": 20,
                "receipt_number": "20250101000001",
            },
        )
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("server_id", "tool_name"),
    [
        (server_id, spec.name)
        for server_id, specs in SPECIALIST_TOOLS.items()
        for spec in specs
    ],
)
async def test_each_public_specialist_tool_dispatches_to_its_registered_server(
    monkeypatch: pytest.MonkeyPatch,
    server_id: str,
    tool_name: str,
) -> None:
    calls: list[tuple[str, str, dict[str, object]]] = []

    class StubRegistry:
        async def call_tool(
            self, called_server_id: str, called_tool_name: str, arguments: dict[str, object]
        ) -> dict[str, object]:
            calls.append((called_server_id, called_tool_name, arguments))
            return {"status": "ok", "server_id": called_server_id, "tool_name": called_tool_name}

    monkeypatch.setattr(server_module, "specialist_registry", StubRegistry())

    async with Client(mcp) as client:
        result = await client.call_tool(
            tool_name,
            {"arguments": {"corp_code": "00126380", "max_items": 5}},
        )

    assert result.data == {"status": "ok", "server_id": server_id, "tool_name": tool_name}
    assert calls == [(server_id, tool_name, {"corp_code": "00126380", "max_items": 5})]
