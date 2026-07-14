"""Deterministic routing across sixteen OpenDART disclosure domains."""

from __future__ import annotations

import re
from typing import Any

ROUTE_CATEGORIES: tuple[dict[str, Any], ...] = (
    {
        "id": "disclosure_search",
        "label_ko": "공시검색/기업개황",
        "terms": (
            "기업 개황",
            "기업개황",
            "회사정보",
            "기업정보",
            "기업코드",
            "종목코드",
            "공시 검색",
            "공시검색",
            "최근 공시",
            "공시",
        ),
        "supported_tools": ("get_company_profile", "search_disclosures"),
    },
    {
        "id": "shareholder_stock",
        "label_ko": "주주/주식 정보",
        "terms": (
            "최대주주",
            "주주 현황",
            "주주현황",
            "소액주주",
            "배당금",
            "배당",
            "지분율",
            "주식총수",
        ),
        "supported_tools": ("get_dividend_information", "get_major_shareholders"),
    },
    {
        "id": "executive_compensation",
        "label_ko": "임원/보수 정보",
        "terms": (
            "임원 보수",
            "임원보수",
            "직원 수",
            "직원수",
            "평균 급여",
            "평균급여",
            "사외이사",
            "임원 현황",
            "직원 현황",
            "연봉",
            "급여",
        ),
        "supported_tools": ("get_employee_statistics",),
    },
    {
        "id": "debt_securities",
        "label_ko": "채무증권 정보",
        "terms": (
            "회사채",
            "기업어음",
            "단기사채",
            "미상환 잔액",
            "미상환잔액",
            "신종자본증권",
            "조건부자본증권",
        ),
        "supported_tools": ("search_disclosures",),
    },
    {
        "id": "audit_fund",
        "label_ko": "감사/자금 정보",
        "terms": (
            "외부 감사인",
            "외부감사인",
            "감사의견",
            "감사 의견",
            "감사보수",
            "감사 보수",
            "자금사용",
            "공모자금",
        ),
        "supported_tools": ("search_disclosures",),
    },
    {
        "id": "financial_statement",
        "label_ko": "재무정보",
        "terms": (
            "연결 재무제표",
            "재무제표",
            "현금흐름",
            "영업이익",
            "매출액",
            "당기순이익",
            "부채비율",
            "재무비율",
            "자산",
        ),
        "supported_tools": ("get_financial_statement",),
    },
    {
        "id": "equity_disclosure",
        "label_ko": "지분공시",
        "terms": (
            "대량보유",
            "5% 보고",
            "5%보고",
            "5%룰",
            "임원 지분",
            "임원지분",
            "임원 주식",
            "지분 변동",
            "지분변동",
            "특수관계인",
        ),
        "supported_tools": ("get_major_shareholders", "search_disclosures"),
    },
    {
        "id": "capital_change",
        "label_ko": "증자감자",
        "terms": ("유상증자", "무상증자", "감자 결정", "감자결정", "자본금변동"),
        "supported_tools": ("search_disclosures",),
    },
    {
        "id": "treasury_stock",
        "label_ko": "자기주식",
        "terms": (
            "자기주식",
            "자사주",
            "바이백",
            "주식 소각",
            "주식소각",
            "신탁계약",
        ),
        "supported_tools": ("search_disclosures",),
    },
    {
        "id": "convertible_securities",
        "label_ko": "전환증권",
        "terms": (
            "전환사채",
            "신주인수권부사채",
            "교환사채",
            "cb 발행",
            "bw 발행",
            "eb 발행",
        ),
        "supported_tools": ("search_disclosures",),
    },
    {
        "id": "merger_division",
        "label_ko": "합병분할",
        "terms": (
            "회사 합병",
            "합병 결정",
            "인적분할",
            "물적분할",
            "분할합병",
            "주식교환",
            "합병",
        ),
        "supported_tools": ("search_disclosures",),
    },
    {
        "id": "business_transfer",
        "label_ko": "영업/자산 양수도",
        "terms": (
            "영업 양도",
            "영업양도",
            "영업 양수",
            "영업양수",
            "자산 양수도",
            "자산양수도",
            "유형자산 양수",
            "유형자산 양도",
        ),
        "supported_tools": ("search_disclosures",),
    },
    {
        "id": "overseas_listing",
        "label_ko": "해외상장",
        "terms": (
            "해외 증권시장",
            "해외증권시장",
            "해외 상장",
            "해외상장",
            "adr 발행",
            "gdr 발행",
            "예탁증서",
        ),
        "supported_tools": ("search_disclosures",),
    },
    {
        "id": "equity_investment",
        "label_ko": "지분거래",
        "terms": (
            "타법인 출자",
            "타법인출자",
            "타법인 주식",
            "타법인주식",
            "자회사 지분",
            "출자증권",
            "지분 취득",
            "지분 처분",
        ),
        "supported_tools": ("search_disclosures",),
    },
    {
        "id": "corporate_issues",
        "label_ko": "기업이슈",
        "terms": (
            "부도 발생",
            "부도발생",
            "회생절차",
            "영업정지",
            "소송",
            "파산",
            "관리절차",
            "해산",
        ),
        "supported_tools": ("search_disclosures",),
    },
    {
        "id": "securities_registration",
        "label_ko": "증권발행/등록정보",
        "terms": (
            "증권신고서",
            "증권 발행",
            "증권발행",
            "등록정보",
            "신주발행",
            "기업공개",
            "ipo",
            "공모",
        ),
        "supported_tools": ("search_disclosures",),
    },
)


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value.casefold())


def _category_match(query: str, category: dict[str, Any]) -> tuple[float, list[str]]:
    compact_query = _compact(query)
    matches: list[str] = []
    raw_score = 0.0

    for term in category["terms"]:
        if _compact(term) not in compact_query:
            continue
        matches.append(term)
        # Longer, domain-specific phrases outweigh generic one-word matches.
        raw_score += 1.0 + min(len(_compact(term)), 12) / 6

    return raw_score, matches


def classify_disclosure_request(query: str, top_k: int = 3) -> dict[str, Any]:
    """Rank all disclosure domains for a natural-language request.

    This function classifies and recommends existing tools. It does not invoke
    independent downstream MCP servers or call an external model.
    """

    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must contain non-whitespace text")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 16:
        raise ValueError("top_k must be an integer from 1 to 16")

    ranked: list[tuple[float, int, dict[str, Any], list[str]]] = []
    for position, category in enumerate(ROUTE_CATEGORIES):
        raw_score, matches = _category_match(query, category)
        ranked.append((raw_score, position, category, matches))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    highest_score = ranked[0][0]
    routes = []
    for raw_score, _position, category, matches in ranked[:top_k]:
        score = raw_score / highest_score if highest_score else 0.0
        routes.append(
            {
                "category": category["id"],
                "label_ko": category["label_ko"],
                "score": round(score, 4),
                "matched_terms": matches,
                "supported_tools": list(category["supported_tools"]),
            }
        )

    return {"query": query, "routes": routes, "total_categories": len(ROUTE_CATEGORIES)}
