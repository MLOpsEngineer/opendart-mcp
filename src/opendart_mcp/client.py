"""Small, bounded async client for OpenDART JSON endpoints."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any

import httpx
from fastmcp.exceptions import ToolError

BASE_URL = "https://opendart.fss.or.kr/api"
MAX_RESPONSE_BYTES = 2_000_000
NO_DATA_STATUS = "013"


class OpenDartClient:
    """Call OpenDART without persisting credentials, requests, or responses."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

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
            async with httpx.AsyncClient(
                base_url=BASE_URL,
                timeout=timeout,
                follow_redirects=False,
            ) as http, http.stream("GET", f"/{endpoint}", params=query) as response:
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
