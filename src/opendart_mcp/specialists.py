"""Sixteen in-process specialist MCP servers backed by OpenDART endpoints."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal

from fastmcp import Client, FastMCP
from mcp.types import ToolAnnotations

from .client import OpenDartClient
from .normalization import (
    validate_business_year,
    validate_corp_code,
    validate_date_range,
    validate_fs_division,
    validate_report_code,
)

ToolKind = Literal[
    "company",
    "corp_codes",
    "direct",
    "document",
    "event",
    "index_multi",
    "index_single",
    "list",
    "periodic",
    "statement",
    "statement_multi",
    "taxonomy",
    "xbrl",
]

SERVICE_DESCRIPTION = "Disclosure Compass(공시나침반) with OpenDART (전자공시시스템 DART)"
SPECIALIST_MCP_PATH_PREFIX = "/specialists"
UPSTREAM_GATEWAY_URL_ENV = "OPENDART_UPSTREAM_GATEWAY_URL"
READ_ONLY_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "openWorldHint": True,
    "idempotentHint": True,
}


@dataclass(frozen=True)
class SpecialistTool:
    name: str
    endpoint: str
    kind: ToolKind
    label: str
    keywords: tuple[str, ...]


def _tool(
    name: str,
    endpoint: str,
    kind: ToolKind,
    label: str,
    *keywords: str,
) -> SpecialistTool:
    return SpecialistTool(name, endpoint, kind, label, tuple(keywords))


# This registry is distilled from the original 16-server implementation in
# dart-mcp-server-experiments. The original public tool names and endpoints are
# intentionally retained so its callers can migrate without an alias layer.
SPECIALIST_TOOLS: dict[str, tuple[SpecialistTool, ...]] = {
    "disclosure_search": (
        _tool("dart_list", "list.json", "list", "공시 검색", "공시", "보고서"),
        _tool("dart_company", "company.json", "company", "기업 개황", "기업 개황", "회사 정보"),
        _tool("dart_document", "document.xml", "document", "공시 원문", "원문", "공시서류"),
        _tool(
            "dart_corpCode", "corpCode.xml", "corp_codes", "기업 고유번호", "고유번호", "기업코드"
        ),
    ),
    "shareholder_stock": (
        _tool(
            "dart_stockTotqySttus",
            "stockTotqySttus.json",
            "periodic",
            "주식 총수",
            "주식총수",
            "발행주식",
        ),
        _tool(
            "dart_irdsSttus",
            "irdsSttus.json",
            "periodic",
            "증자·감자 현황",
            "증자 이력",
            "감자 이력",
        ),
        _tool("dart_alotMatter", "alotMatter.json", "periodic", "배당 사항", "배당", "배당금"),
        _tool(
            "dart_tesstkAcqsDspsSttus",
            "tesstkAcqsDspsSttus.json",
            "periodic",
            "자기주식 취득·처분 현황",
            "자기주식 현황",
            "자사주 현황",
        ),
        _tool("dart_hyslrSttus", "hyslrSttus.json", "periodic", "최대주주 현황", "최대주주"),
        _tool(
            "dart_hyslrChgSttus", "hyslrChgSttus.json", "periodic", "최대주주 변동", "최대주주 변동"
        ),
        _tool("dart_mrhlSttus", "mrhlSttus.json", "periodic", "소액주주 현황", "소액주주"),
        _tool(
            "dart_otrCprInvstmntSttus",
            "otrCprInvstmntSttus.json",
            "periodic",
            "타법인 출자현황",
            "타법인 출자현황",
        ),
    ),
    "executive_compensation": (
        _tool("dart_exctvSttus", "exctvSttus.json", "periodic", "임원 현황", "임원 현황"),
        _tool("dart_empSttus", "empSttus.json", "periodic", "직원 현황", "직원 현황", "직원 수"),
        _tool(
            "dart_outcmpnyDrctrNdChangeSttus",
            "outcmpnyDrctrNdChangeSttus.json",
            "periodic",
            "사외이사 변동",
            "사외이사",
        ),
        _tool(
            "dart_hmvAuditIndvdlBySttus",
            "hmvAuditIndvdlBySttus.json",
            "periodic",
            "이사·감사 개인별 보수",
            "개인별 보수",
            "5억 이상 보수",
        ),
        _tool(
            "dart_hmvAuditAllSttus",
            "hmvAuditAllSttus.json",
            "periodic",
            "등기임원 전체 보수",
            "등기임원 보수",
        ),
        _tool(
            "dart_indvdlByPay",
            "indvdlByPay.json",
            "periodic",
            "개인별 보수지급",
            "보수 상위",
            "보수지급",
        ),
        _tool(
            "dart_unrstExctvMendngSttus",
            "unrstExctvMendngSttus.json",
            "periodic",
            "미등기임원 보수",
            "미등기임원",
        ),
        _tool(
            "dart_drctrAdtAllMendngSttusGmtsckConfmAmount",
            "drctrAdtAllMendngSttusGmtsckConfmAmount.json",
            "periodic",
            "임원 보수한도 승인액",
            "보수한도",
            "승인금액",
        ),
        _tool(
            "dart_drctrAdtAllMendngSttusMendngPymntamtTyCl",
            "drctrAdtAllMendngSttusMendngPymntamtTyCl.json",
            "periodic",
            "임원 유형별 보수",
            "유형별 보수",
        ),
    ),
    "debt_securities": (
        _tool(
            "dart_detScritsIsuAcmslt",
            "detScritsIsuAcmslt.json",
            "periodic",
            "채무증권 발행실적",
            "발행실적",
        ),
        _tool(
            "dart_entrprsBilScritsNrdmpBlce",
            "entrprsBilScritsNrdmpBlce.json",
            "periodic",
            "기업어음 미상환",
            "기업어음",
        ),
        _tool(
            "dart_srtpdPsndbtNrdmpBlce",
            "srtpdPsndbtNrdmpBlce.json",
            "periodic",
            "단기사채 미상환",
            "단기사채",
        ),
        _tool("dart_cprndNrdmpBlce", "cprndNrdmpBlce.json", "periodic", "회사채 미상환", "회사채"),
        _tool(
            "dart_newCaplScritsNrdmpBlce",
            "newCaplScritsNrdmpBlce.json",
            "periodic",
            "신종자본증권 미상환",
            "신종자본증권",
        ),
        _tool(
            "dart_cndlCaplScritsNrdmpBlce",
            "cndlCaplScritsNrdmpBlce.json",
            "periodic",
            "조건부자본증권 미상환",
            "조건부자본증권",
        ),
    ),
    "audit_fund": (
        _tool(
            "dart_accnutAdtorNmNdAdtOpinion",
            "accnutAdtorNmNdAdtOpinion.json",
            "periodic",
            "감사인 및 감사의견",
            "감사의견",
            "감사인",
        ),
        _tool(
            "dart_adtServcCnclsSttus",
            "adtServcCnclsSttus.json",
            "periodic",
            "감사용역 계약",
            "감사용역",
        ),
        _tool(
            "dart_accnutAdtorNonAdtServcCnclsSttus",
            "accnutAdtorNonAdtServcCnclsSttus.json",
            "periodic",
            "비감사용역 계약",
            "비감사용역",
            "세무자문",
        ),
        _tool(
            "dart_pssrpCptalUseDtls",
            "pssrpCptalUseDtls.json",
            "periodic",
            "공모자금 사용",
            "공모자금",
            "ipo 자금",
        ),
        _tool(
            "dart_prvsrpCptalUseDtls",
            "prvsrpCptalUseDtls.json",
            "periodic",
            "사모자금 사용",
            "사모자금",
            "제3자배정 자금",
        ),
    ),
    "financial_statement": (
        _tool(
            "dart_fnlttSinglAcnt",
            "fnlttSinglAcnt.json",
            "statement",
            "단일회사 주요계정",
            "주요계정",
        ),
        _tool(
            "dart_fnlttMultiAcnt",
            "fnlttMultiAcnt.json",
            "statement_multi",
            "다중회사 주요계정",
            "다중회사",
            "회사 비교",
        ),
        _tool("dart_fnlttXbrl", "fnlttXbrl.xml", "xbrl", "XBRL 원본", "xbrl 원본"),
        _tool(
            "dart_fnlttSinglAcntAll",
            "fnlttSinglAcntAll.json",
            "statement",
            "전체 재무제표",
            "전체 재무제표",
            "재무제표",
        ),
        _tool(
            "dart_xbrlTaxonomy",
            "xbrlTaxonomy.json",
            "taxonomy",
            "XBRL 택사노미",
            "택사노미",
            "재무제표 양식",
        ),
        _tool(
            "dart_fnlttSinglIndx",
            "fnlttSinglIndx.json",
            "index_single",
            "단일회사 재무비율",
            "재무비율",
            "재무지표",
        ),
        _tool(
            "dart_fnlttCmpnyIndx",
            "fnlttCmpnyIndx.json",
            "index_multi",
            "다중회사 재무비율",
            "재무비율 비교",
            "지표 비교",
        ),
    ),
    "equity_disclosure": (
        _tool(
            "dart_majorstock",
            "majorstock.json",
            "direct",
            "5% 대량보유",
            "대량보유",
            "5%룰",
            "5% 보고",
        ),
        _tool(
            "dart_elestock",
            "elestock.json",
            "direct",
            "임원·주요주주 소유",
            "임원 지분",
            "주요주주 소유",
        ),
    ),
    "securities_registration": (
        _tool("dart_estkRs", "estkRs.json", "event", "지분증권 신고서", "지분증권", "주식 신고서"),
        _tool("dart_bdRs", "bdRs.json", "event", "채무증권 신고서", "채무증권"),
        _tool("dart_stkdpRs", "stkdpRs.json", "event", "예탁증권 신고서", "예탁증권", "dr 신고"),
        _tool("dart_mgRs", "mgRs.json", "event", "합병 신고서", "합병 신고서"),
        _tool(
            "dart_extrRs",
            "extrRs.json",
            "event",
            "주식교환·이전 신고서",
            "교환 신고서",
            "이전 신고서",
        ),
        _tool("dart_dvRs", "dvRs.json", "event", "분할 신고서", "분할 신고서"),
    ),
    "capital_change": (
        _tool("dart_piicDecsn", "piicDecsn.json", "event", "유상증자 결정", "유상증자"),
        _tool("dart_fricDecsn", "fricDecsn.json", "event", "무상증자 결정", "무상증자"),
        _tool("dart_pifricDecsn", "pifricDecsn.json", "event", "유무상증자 결정", "유무상증자"),
        _tool("dart_crDecsn", "crDecsn.json", "event", "감자 결정", "감자"),
    ),
    "treasury_stock": (
        _tool(
            "dart_tsstkAqDecsn",
            "tsstkAqDecsn.json",
            "event",
            "자기주식 취득 결정",
            "자기주식 취득",
            "자사주 매입",
        ),
        _tool(
            "dart_tsstkDpDecsn",
            "tsstkDpDecsn.json",
            "event",
            "자기주식 처분 결정",
            "자기주식 처분",
            "자사주 매각",
        ),
        _tool(
            "dart_tsstkAqTrctrCnsDecsn",
            "tsstkAqTrctrCnsDecsn.json",
            "event",
            "자기주식 신탁계약 체결",
            "신탁계약 체결",
        ),
        _tool(
            "dart_tsstkAqTrctrCcDecsn",
            "tsstkAqTrctrCcDecsn.json",
            "event",
            "자기주식 신탁계약 해지",
            "신탁계약 해지",
        ),
    ),
    "convertible_securities": (
        _tool(
            "dart_cvbdIsDecsn", "cvbdIsDecsn.json", "event", "전환사채 발행", "전환사채", "cb 발행"
        ),
        _tool(
            "dart_bdwtIsDecsn",
            "bdwtIsDecsn.json",
            "event",
            "신주인수권부사채 발행",
            "신주인수권부사채",
            "bw 발행",
        ),
        _tool(
            "dart_exbdIsDecsn", "exbdIsDecsn.json", "event", "교환사채 발행", "교환사채", "eb 발행"
        ),
        _tool(
            "dart_wdCocobdIsDecsn",
            "wdCocobdIsDecsn.json",
            "event",
            "조건부자본증권 발행",
            "코코본드",
            "상각형 조건부자본",
        ),
    ),
    "merger_division": (
        _tool("dart_cmpMgDecsn", "cmpMgDecsn.json", "event", "합병 결정", "합병 결정", "회사 합병"),
        _tool(
            "dart_cmpDvDecsn",
            "cmpDvDecsn.json",
            "event",
            "분할 결정",
            "분할 결정",
            "인적분할",
            "물적분할",
        ),
        _tool("dart_cmpDvmgDecsn", "cmpDvmgDecsn.json", "event", "분할합병 결정", "분할합병"),
        _tool(
            "dart_stkExtrDecsn",
            "stkExtrDecsn.json",
            "event",
            "주식교환·이전 결정",
            "주식교환",
            "주식이전",
        ),
    ),
    "business_transfer": (
        _tool("dart_bsnInhDecsn", "bsnInhDecsn.json", "event", "영업양수 결정", "영업양수"),
        _tool("dart_bsnTrfDecsn", "bsnTrfDecsn.json", "event", "영업양도 결정", "영업양도"),
        _tool(
            "dart_tgastInhDecsn",
            "tgastInhDecsn.json",
            "event",
            "유형자산 양수",
            "유형자산 양수",
            "설비 취득",
        ),
        _tool(
            "dart_tgastTrfDecsn", "tgastTrfDecsn.json", "event", "유형자산 양도", "유형자산 양도"
        ),
        _tool(
            "dart_stkrtbdInhDecsn",
            "stkrtbdInhDecsn.json",
            "event",
            "주권관련 사채권 양수",
            "사채권 양수",
            "cb 취득",
            "bw 취득",
        ),
    ),
    "overseas_listing": (
        _tool("dart_ovLstDecsn", "ovLstDecsn.json", "event", "해외상장 결정", "해외상장 결정"),
        _tool(
            "dart_ovDlstDecsn",
            "ovDlstDecsn.json",
            "event",
            "해외상장폐지 결정",
            "해외상장폐지 결정",
        ),
        _tool("dart_ovLst", "ovLst.json", "event", "해외시장 상장", "해외시장 상장", "해외 상장"),
        _tool(
            "dart_ovDlst",
            "ovDlst.json",
            "event",
            "해외시장 상장폐지",
            "해외시장 상장폐지",
            "해외 상장폐지",
        ),
    ),
    "equity_investment": (
        _tool(
            "dart_otcprStkInvscr",
            "otcprStkInvscr.json",
            "event",
            "타법인주식 취득",
            "타법인주식 취득",
            "지분 취득",
        ),
        _tool(
            "dart_otcprStkInvscrInhDecsn",
            "otcprStkInvscrInhDecsn.json",
            "event",
            "타법인주식 양수",
            "타법인주식 양수",
            "지분 양수",
        ),
        _tool(
            "dart_otcprStkInvscrTrfDecsn",
            "otcprStkInvscrTrfDecsn.json",
            "event",
            "타법인주식 양도",
            "타법인주식 양도",
            "지분 양도",
            "지분 처분",
        ),
    ),
    "corporate_issues": (
        _tool(
            "dart_bnkMngtPcbg",
            "bnkMngtPcbg.json",
            "event",
            "채권은행 관리절차",
            "관리절차",
            "채권은행",
        ),
        _tool("dart_dsRsOcr", "dsRsOcr.json", "event", "해산사유 발생", "해산"),
        _tool("dart_dfOcr", "dfOcr.json", "event", "부도 발생", "부도"),
        _tool("dart_bsnSp", "bsnSp.json", "event", "영업정지", "영업정지"),
        _tool(
            "dart_ctrcvsBgrq",
            "ctrcvsBgrq.json",
            "event",
            "회생절차 개시",
            "회생절차 개시",
            "회생 신청",
        ),
        _tool(
            "dart_rhbPcEnd", "rhbPcEnd.json", "event", "회생절차 종결", "회생절차 종결", "회생 종료"
        ),
        _tool("dart_lwstLg", "lwstLg.json", "event", "소송 제기", "소송"),
    ),
}


def specialist_tool_count() -> int:
    return sum(len(tools) for tools in SPECIALIST_TOOLS.values())


def specialist_mcp_path(server_id: str) -> str:
    """Return the public Streamable HTTP path for one specialist MCP server."""

    if server_id not in SPECIALIST_TOOLS:
        raise ValueError(f"unknown disclosure server: {server_id}")
    return f"{SPECIALIST_MCP_PATH_PREFIX}/{server_id}/mcp"


def list_specialists(server_id: str | None = None) -> dict[str, Any]:
    if server_id is not None and server_id not in SPECIALIST_TOOLS:
        raise ValueError(f"unknown disclosure server: {server_id}")
    selected = (
        {server_id: SPECIALIST_TOOLS[server_id]} if server_id is not None else SPECIALIST_TOOLS
    )
    return {
        "server_count": len(SPECIALIST_TOOLS),
        "tool_count": specialist_tool_count(),
        "servers": [
            {
                "server_id": current_id,
                "tool_count": len(tools),
                "tools": [
                    {
                        "name": tool.name,
                        "endpoint": tool.endpoint,
                        "label_ko": tool.label,
                    }
                    for tool in tools
                ],
            }
            for current_id, tools in selected.items()
        ],
    }


def select_specialist_tool(server_id: str, query: str) -> SpecialistTool:
    if server_id not in SPECIALIST_TOOLS:
        raise ValueError(f"unknown disclosure server: {server_id}")
    normalized = " ".join(query.casefold().split())
    tools = SPECIALIST_TOOLS[server_id]
    ranked = []
    for position, tool in enumerate(tools):
        score = sum(len(keyword) for keyword in tool.keywords if keyword.casefold() in normalized)
        ranked.append((score, -position, tool))
    score, _position, selected = max(ranked, key=lambda item: (item[0], item[1]))
    if score == 0 and server_id == "disclosure_search":
        return tools[0]
    return selected


class SpecialistServerRegistry:
    """Create and call the original domain tools through FastMCP in-memory clients."""

    def __init__(
        self,
        dart_client: OpenDartClient,
        upstream_gateway_url: str | None = None,
    ) -> None:
        self._dart_client = dart_client
        self._upstream_gateway_url = (
            upstream_gateway_url or os.getenv(UPSTREAM_GATEWAY_URL_ENV, "")
        ).rstrip("/")
        self._servers = {
            server_id: self._build_server(server_id, tools)
            for server_id, tools in SPECIALIST_TOOLS.items()
        }

    def _build_server(self, server_id: str, tools: tuple[SpecialistTool, ...]) -> FastMCP:
        server = FastMCP(
            f"Disclosure Compass specialist: {server_id}",
            instructions=(
                f"Use {SERVICE_DESCRIPTION} read-only specialist tools for the "
                f"{server_id} disclosure domain. Provide either an eight-digit OpenDART "
                "company code or a Korean company name when a tool needs a company."
            ),
            version="1.2.2",
        )
        for spec in tools:
            self._register_tool(server, server_id, spec)
        return server

    def _register_tool(self, server: FastMCP, server_id: str, spec: SpecialistTool) -> None:
        async def invoke(arguments: dict[str, Any]) -> dict[str, Any]:
            return await self._invoke_specialist_tool(server_id, spec, arguments)

        server.tool(
            name=spec.name,
            title=f"{server_id}: {spec.label}",
            description=(
                f"Use {SERVICE_DESCRIPTION} to retrieve {spec.label} through the "
                f"{server_id} disclosure domain. This read-only specialist tool calls "
                f"OpenDART endpoint {spec.endpoint}."
            ),
            annotations=ToolAnnotations(
                title=f"{server_id}: {spec.label}", **READ_ONLY_ANNOTATIONS
            ),
            tags={"opendart", "specialist", server_id},
        )(invoke)

    def get_server(self, server_id: str) -> FastMCP:
        """Return one public-ready specialist FastMCP server by its canonical ID."""

        return self._server(server_id)

    async def list_tools(self, server_id: str) -> list[str]:
        server = self._server(server_id)
        async with Client(server) as client:
            return [tool.name for tool in await client.list_tools()]

    async def call_tool(
        self, server_id: str, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        server = self._server(server_id)
        allowed = {tool.name for tool in SPECIALIST_TOOLS[server_id]}
        if tool_name not in allowed:
            raise ValueError(f"unknown tool '{tool_name}' for server '{server_id}'")
        async with Client(server) as client:
            result = await client.call_tool(tool_name, {"arguments": arguments})
        return result.data

    def _server(self, server_id: str) -> FastMCP:
        try:
            return self._servers[server_id]
        except KeyError as exc:
            raise ValueError(f"unknown disclosure server: {server_id}") from exc

    async def _invoke_specialist_tool(
        self, server_id: str, spec: SpecialistTool, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        if self._upstream_gateway_url:
            return await self._call_upstream(server_id, spec.name, arguments)
        return await self._execute(server_id, spec, arguments)

    async def _call_upstream(
        self, server_id: str, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Use a compatible gateway when this public edge has no DART secret."""

        async with Client(self._upstream_gateway_url) as upstream:
            result = await upstream.call_tool(
                "call_disclosure_server_tool",
                {
                    "server_id": server_id,
                    "tool_name": tool_name,
                    "arguments": arguments,
                },
            )
        return result.data

    async def _resolve_corp_code(self, arguments: dict[str, Any]) -> str:
        if arguments.get("corp_code"):
            return validate_corp_code(str(arguments["corp_code"]))
        corp_name = str(arguments.get("corp_name", "")).strip()
        if not corp_name:
            raise ValueError("corp_code or corp_name is required")
        return await self._dart_client.resolve_corp_code(corp_name)

    async def _execute(
        self, server_id: str, spec: SpecialistTool, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        args = dict(arguments or {})
        max_items = int(args.pop("max_items", 20))
        if not 1 <= max_items <= 50:
            raise ValueError("max_items must be between 1 and 50")

        if spec.kind == "corp_codes":
            corp_name = str(args.get("corp_name", "")).strip()
            if not corp_name:
                raise ValueError("corp_name is required")
            data = await self._dart_client.search_corp_codes(corp_name, max_items)
            return self._result(server_id, spec, data, len(data))

        if spec.kind in {"document", "xbrl"}:
            receipt_number = str(args.get("receipt_number") or args.get("rcept_no") or "").strip()
            if len(receipt_number) != 14 or not receipt_number.isdigit():
                raise ValueError("receipt_number must contain exactly 14 digits")
            params: dict[str, str | int | None] = {"rcept_no": receipt_number}
            if spec.kind == "xbrl":
                params["reprt_code"] = validate_report_code(
                    str(args.get("report_code") or args.get("reprt_code") or "11011")
                )
            metadata = await self._dart_client.get_binary_metadata(spec.endpoint, params)
            return self._result(server_id, spec, metadata)

        if spec.kind == "taxonomy":
            statement_type = (
                str(args.get("statement_type") or args.get("sj_div") or "").strip().upper()
            )
            if statement_type not in {
                "BS1",
                "BS2",
                "BS3",
                "BS4",
                "IS1",
                "IS2",
                "IS3",
                "IS4",
                "CIS1",
                "CIS2",
                "CIS3",
                "CIS4",
                "CF1",
                "CF2",
                "SCE1",
            }:
                raise ValueError("statement_type is not a supported XBRL taxonomy code")
            payload = await self._dart_client.get_json(spec.endpoint, {"sj_div": statement_type})
            return self._payload_result(server_id, spec, payload, max_items)

        if spec.kind == "list":
            has_company = bool(args.get("corp_code") or args.get("corp_name"))
            begin_date, end_date = self._dates(args, default_days=365 if has_company else 90)
            corp_code = None
            if args.get("corp_code") or args.get("corp_name"):
                corp_code = await self._resolve_corp_code(args)
            payload = await self._dart_client.get_json(
                spec.endpoint,
                {
                    "corp_code": corp_code,
                    "bgn_de": begin_date,
                    "end_de": end_date,
                    "pblntf_ty": args.get("disclosure_type") or args.get("pblntf_ty"),
                    "page_no": 1,
                    "page_count": max_items,
                    "sort": "date",
                    "sort_mth": "desc",
                },
            )
            return self._payload_result(server_id, spec, payload, max_items)

        if spec.kind == "company":
            corp_code = await self._resolve_corp_code(args)
            payload = await self._dart_client.get_json(spec.endpoint, {"corp_code": corp_code})
            return self._payload_result(server_id, spec, payload, max_items)

        params: dict[str, str | int | None]
        if spec.kind in {"statement_multi", "index_multi"}:
            corp_codes = args.get("corp_codes")
            if not isinstance(corp_codes, list) or not corp_codes:
                raise ValueError("corp_codes must be a non-empty list")
            validated_codes = [validate_corp_code(str(value)) for value in corp_codes]
            if len(validated_codes) > 10:
                raise ValueError("corp_codes must contain at most 10 companies")
            params = {"corp_code": ",".join(validated_codes)}
        else:
            params = {"corp_code": await self._resolve_corp_code(args)}

        if spec.kind in {"event"}:
            begin_date, end_date = self._dates(args)
            params.update({"bgn_de": begin_date, "end_de": end_date})
        elif spec.kind in {
            "periodic",
            "statement",
            "statement_multi",
            "index_single",
            "index_multi",
        }:
            params.update(
                {
                    "bsns_year": validate_business_year(
                        str(
                            args.get("business_year")
                            or args.get("bsns_year")
                            or date.today().year - 1
                        )
                    ),
                    "reprt_code": validate_report_code(
                        str(args.get("report_code") or args.get("reprt_code") or "11011")
                    ),
                }
            )
        if spec.kind in {"statement", "statement_multi"}:
            params["fs_div"] = validate_fs_division(
                str(args.get("fs_division") or args.get("fs_div") or "CFS")
            )
        if spec.kind in {"index_single", "index_multi"}:
            index_code = (
                str(args.get("index_code") or args.get("idx_cl_code") or "M210000").strip().upper()
            )
            if index_code not in {"M210000", "M220000", "M230000", "M240000"}:
                raise ValueError("index_code must be M210000, M220000, M230000, or M240000")
            params["idx_cl_code"] = index_code

        payload = await self._dart_client.get_json(spec.endpoint, params)
        return self._payload_result(server_id, spec, payload, max_items)

    @staticmethod
    def _dates(arguments: dict[str, Any], *, default_days: int = 365) -> tuple[str, str]:
        today = date.today()
        begin_date = str(
            arguments.get("begin_date")
            or arguments.get("bgn_de")
            or (today - timedelta(days=default_days)).strftime("%Y%m%d")
        )
        end_date = str(
            arguments.get("end_date") or arguments.get("end_de") or today.strftime("%Y%m%d")
        )
        return validate_date_range(begin_date, end_date)

    def _payload_result(
        self,
        server_id: str,
        spec: SpecialistTool,
        payload: dict[str, Any],
        max_items: int,
    ) -> dict[str, Any]:
        data: Any = payload
        count = None
        if isinstance(payload.get("list"), list):
            data = payload["list"][:max_items]
            count = len(data)
        else:
            data = {
                key: value for key, value in payload.items() if key not in {"status", "message"}
            }
        return self._result(server_id, spec, data, count)

    @staticmethod
    def _result(
        server_id: str,
        spec: SpecialistTool,
        data: Any,
        count: int | None = None,
    ) -> dict[str, Any]:
        response = {
            "status": "ok",
            "server_id": server_id,
            "tool_name": spec.name,
            "endpoint": spec.endpoint,
            "data": data,
        }
        if count is not None:
            response["count"] = count
        return response
