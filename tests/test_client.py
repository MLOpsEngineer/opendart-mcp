from __future__ import annotations

import io
import zipfile

import pytest
from fastmcp.exceptions import ToolError

from opendart_mcp.client import OpenDartClient


def zip_bytes(filename: str, contents: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(filename, contents)
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_search_corp_codes_downloads_parses_and_caches_archive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = OpenDartClient("test-key")
    archive = zip_bytes(
        "CORPCODE.xml",
        """<result>
        <list><corp_code>00126380</corp_code><corp_name>삼성전자</corp_name><stock_code>005930</stock_code></list>
        <list><corp_code>00293886</corp_code><corp_name>삼성전자서비스</corp_name><stock_code></stock_code></list>
        </result>""",
    )
    calls = 0

    async def fake_get_bytes(endpoint: str, params: dict[str, object]) -> bytes:
        nonlocal calls
        calls += 1
        assert endpoint == "corpCode.xml"
        assert params == {}
        return archive

    monkeypatch.setattr(client, "_get_bytes", fake_get_bytes)

    exact = await client.search_corp_codes("005930")
    partial = await client.search_corp_codes("삼성전자")

    assert exact[0]["corp_code"] == "00126380"
    assert [row["corp_code"] for row in partial] == ["00126380", "00293886"]
    assert await client.resolve_corp_code("삼성전자") == "00126380"
    assert calls == 1


@pytest.mark.asyncio
async def test_binary_artifact_returns_metadata_without_raw_contents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = OpenDartClient("test-key")
    archive = zip_bytes("filing.xml", "<document>public filing</document>")

    async def fake_get_bytes(endpoint: str, params: dict[str, object]) -> bytes:
        assert endpoint == "document.xml"
        assert params == {"rcept_no": "20250101000001"}
        return archive

    monkeypatch.setattr(client, "_get_bytes", fake_get_bytes)

    metadata = await client.get_binary_metadata("document.xml", {"rcept_no": "20250101000001"})

    assert metadata["content_type"] == "application/zip"
    assert metadata["content_length"] == len(archive)
    assert len(metadata["sha256"]) == 64
    assert metadata["files"] == [{"name": "filing.xml", "size": 34}]
    assert "public filing" not in str(metadata)


@pytest.mark.asyncio
async def test_binary_artifact_rejects_corrupt_zip(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenDartClient("test-key")

    async def fake_get_bytes(endpoint: str, params: dict[str, object]) -> bytes:
        return b"PK-not-a-zip"

    monkeypatch.setattr(client, "_get_bytes", fake_get_bytes)

    with pytest.raises(ToolError, match="corrupt binary archive"):
        await client.get_binary_metadata("document.xml", {"rcept_no": "20250101000001"})
