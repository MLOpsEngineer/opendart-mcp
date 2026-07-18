from __future__ import annotations

import json
import re

import pytest
from fastmcp import Client
from starlette.testclient import TestClient

import opendart_mcp.server as server_module
from opendart_mcp.server import app, create_app, mcp
from opendart_mcp.specialists import (
    SPECIALIST_TOOLS,
    specialist_mcp_path,
    specialist_tool_count,
)


@pytest.mark.asyncio
async def test_gateway_mcp_exposes_only_its_ten_orchestration_tools() -> None:
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
    assert {tool.name for tool in tools} == gateway_tool_names
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


@pytest.mark.asyncio
async def test_sixteen_public_specialist_mcps_partition_all_eighty_two_tools() -> None:
    mounted_paths = {route.path for route in app.routes}
    discovered_tool_names: set[str] = set()

    assert len(SPECIALIST_TOOLS) == 16
    assert specialist_tool_count() == 82
    for server_id, specs in SPECIALIST_TOOLS.items():
        public_path = specialist_mcp_path(server_id)
        assert public_path.removesuffix("/mcp") in mounted_paths

        async with Client(server_module.specialist_registry.get_server(server_id)) as client:
            tools = await client.list_tools()

        assert {tool.name for tool in tools} == {spec.name for spec in specs}
        assert 1 <= len(tools) <= 20
        discovered_tool_names.update(tool.name for tool in tools)
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

    assert len(discovered_tool_names) == 82


def test_health_endpoint() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "opendart-mcp",
        "version": "1.2.0",
    }


def test_mounted_specialist_http_endpoint_serves_its_tool_catalog() -> None:
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {},
    }
    with TestClient(create_app()) as client:
        response = client.post(
            specialist_mcp_path("financial_statement"),
            json=request,
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    payload = json.loads(response.text.split("data: ", maxsplit=1)[1])
    assert {tool["name"] for tool in payload["result"]["tools"]} == {
        spec.name for spec in SPECIALIST_TOOLS["financial_statement"]
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
