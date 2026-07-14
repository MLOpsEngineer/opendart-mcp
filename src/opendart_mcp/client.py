"""Small, bounded async client for OpenDART JSON endpoints."""

from __future__ import annotations

import hashlib
import io
import json
import os
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Mapping
from typing import Any

import httpx
from fastmcp.exceptions import ToolError

BASE_URL = "https://opendart.fss.or.kr/api"
MAX_RESPONSE_BYTES = 2_000_000
MAX_BINARY_BYTES = 8_000_000
NO_DATA_STATUS = "013"


class OpenDartClient:
    """Call OpenDART without persisting credentials, requests, or responses."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key
        self._corp_code_rows: list[dict[str, str]] | None = None

    def _require_api_key(self) -> str:
        key = (self._api_key or os.getenv("DART_API_KEY", "")).strip()
        if not key:
            raise ToolError("DART_API_KEY is not configured on the server.")
        return key

    async def get_json(
        self, endpoint: str, params: Mapping[str, str | int | None]
    ) -> dict[str, Any]:
        """Fetch one JSON response with strict time and size bounds."""
        query = {key: str(value) for key, value in params.items() if value is not None}
        query["crtfc_key"] = self._require_api_key()
        timeout = httpx.Timeout(10.0, connect=3.0, read=10.0, write=5.0, pool=3.0)

        try:
            async with (
                httpx.AsyncClient(
                    base_url=BASE_URL,
                    timeout=timeout,
                    follow_redirects=False,
                ) as http,
                http.stream("GET", f"/{endpoint}", params=query) as response,
            ):
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise ToolError("OpenDART response exceeded the 2 MB safety limit.")
        except ToolError:
            raise
        except httpx.TimeoutException as exc:
            raise ToolError("OpenDART did not respond within 10 seconds.") from exc
        except httpx.HTTPStatusError as exc:
            raise ToolError(f"OpenDART returned HTTP {exc.response.status_code}.") from exc
        except httpx.RequestError as exc:
            raise ToolError("OpenDART is temporarily unreachable.") from exc

        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ToolError("OpenDART returned an invalid JSON response.") from exc
        if not isinstance(payload, dict):
            raise ToolError("OpenDART returned an unexpected response shape.")

        status = str(payload.get("status", ""))
        if status == NO_DATA_STATUS:
            return {"status": status, "message": "No data", "list": []}
        if status != "000":
            message = " ".join(str(payload.get("message", "Unknown error")).split())[:160]
            raise ToolError(f"OpenDART error {status or 'unknown'}: {message}")
        return payload

    async def _get_bytes(
        self,
        endpoint: str,
        params: Mapping[str, str | int | None],
        *,
        max_bytes: int = MAX_BINARY_BYTES,
    ) -> bytes:
        query = {key: str(value) for key, value in params.items() if value is not None}
        query["crtfc_key"] = self._require_api_key()
        timeout = httpx.Timeout(20.0, connect=3.0, read=20.0, write=5.0, pool=3.0)
        try:
            async with (
                httpx.AsyncClient(
                    base_url=BASE_URL,
                    timeout=timeout,
                    follow_redirects=False,
                ) as http,
                http.stream("GET", f"/{endpoint}", params=query) as response,
            ):
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise ToolError(
                            f"OpenDART binary response exceeded the {max_bytes} byte limit."
                        )
        except ToolError:
            raise
        except httpx.TimeoutException as exc:
            raise ToolError("OpenDART did not respond within 20 seconds.") from exc
        except httpx.HTTPStatusError as exc:
            raise ToolError(f"OpenDART returned HTTP {exc.response.status_code}.") from exc
        except httpx.RequestError as exc:
            raise ToolError("OpenDART is temporarily unreachable.") from exc
        return bytes(body)

    async def get_binary_metadata(
        self, endpoint: str, params: Mapping[str, str | int | None]
    ) -> dict[str, Any]:
        """Fetch a bounded binary artifact without returning its raw contents."""
        body = await self._get_bytes(endpoint, params)
        if body[:2] != b"PK":
            try:
                root = ET.fromstring(body)
                status = root.findtext("status", "unknown")
                message = " ".join((root.findtext("message") or "Unknown error").split())
            except ET.ParseError as exc:
                raise ToolError("OpenDART returned an invalid binary response.") from exc
            raise ToolError(f"OpenDART error {status}: {message[:160]}")
        try:
            with zipfile.ZipFile(io.BytesIO(body)) as archive:
                files = [
                    {"name": info.filename, "size": info.file_size}
                    for info in archive.infolist()[:20]
                ]
        except zipfile.BadZipFile as exc:
            raise ToolError("OpenDART returned a corrupt binary archive.") from exc
        return {
            "content_type": "application/zip",
            "content_length": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
            "files": files,
        }

    async def _load_corp_codes(self) -> list[dict[str, str]]:
        if self._corp_code_rows is not None:
            return self._corp_code_rows
        body = await self._get_bytes("corpCode.xml", {})
        try:
            with zipfile.ZipFile(io.BytesIO(body)) as archive:
                xml_name = next(
                    name for name in archive.namelist() if name.upper().endswith(".XML")
                )
                root = ET.fromstring(archive.read(xml_name))
        except (zipfile.BadZipFile, StopIteration, ET.ParseError) as exc:
            raise ToolError("OpenDART returned an invalid corporation-code archive.") from exc
        rows = []
        for item in root.findall("list"):
            corp_code = (item.findtext("corp_code") or "").strip()
            corp_name = (item.findtext("corp_name") or "").strip()
            stock_code = (item.findtext("stock_code") or "").strip()
            if corp_code and corp_name:
                rows.append(
                    {
                        "corp_code": corp_code,
                        "corp_name": corp_name,
                        "stock_code": stock_code,
                    }
                )
        self._corp_code_rows = rows
        return rows

    async def search_corp_codes(self, corp_name: str, max_items: int = 10) -> list[dict[str, str]]:
        query = "".join(corp_name.split()).casefold()
        if not query:
            raise ValueError("corp_name is required")
        rows = await self._load_corp_codes()
        exact = []
        partial = []
        for row in rows:
            normalized_name = "".join(row["corp_name"].split()).casefold()
            normalized_stock = row["stock_code"].casefold()
            if query in {normalized_name, normalized_stock}:
                exact.append(row)
            elif query in normalized_name:
                partial.append(row)
        return (exact + partial)[:max_items]

    async def resolve_corp_code(self, corp_name: str) -> str:
        matches = await self.search_corp_codes(corp_name, 2)
        if not matches:
            raise ToolError(f"No OpenDART corporation matched '{corp_name}'.")
        normalized = "".join(corp_name.split()).casefold()
        exact = [
            row
            for row in matches
            if normalized
            in {
                "".join(row["corp_name"].split()).casefold(),
                row["stock_code"].casefold(),
            }
        ]
        if exact:
            return exact[0]["corp_code"]
        if len(matches) > 1:
            raise ToolError("Company name is ambiguous; use an eight-digit corp_code instead.")
        return matches[0]["corp_code"]
