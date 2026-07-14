from __future__ import annotations

import re

import pytest
from fastmcp import Client
from starlette.testclient import TestClient

from opendart_mcp.server import app, mcp


@pytest.mark.asyncio
async def test_mcp_exposes_seven_curated_tools_with_complete_annotations() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()

    assert len(tools) == 7
    assert {tool.name for tool in tools} == {
        "get_company_profile",
        "search_disclosures",
        "get_financial_statement",
        "get_dividend_information",
        "get_major_shareholders",
        "get_employee_statistics",
        "classify_disclosure_request",
    }
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
        "version": "1.0.0",
    }
