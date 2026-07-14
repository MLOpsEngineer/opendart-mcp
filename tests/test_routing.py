from __future__ import annotations

import pytest

from opendart_mcp.routing import ROUTE_CATEGORIES, classify_disclosure_request

EXPECTED_CATEGORY_IDS = {
    "disclosure_search",
    "shareholder_stock",
    "executive_compensation",
    "debt_securities",
    "audit_fund",
    "financial_statement",
    "equity_disclosure",
    "capital_change",
    "treasury_stock",
    "convertible_securities",
    "merger_division",
    "business_transfer",
    "overseas_listing",
    "equity_investment",
    "corporate_issues",
    "securities_registration",
}

STRONG_KOREAN_QUERIES = [
    ("기업 개황 회사정보 종목코드와 기업코드를 조회해줘", "disclosure_search"),
    ("최대주주 지분율과 배당금 주주 현황을 알려줘", "shareholder_stock"),
    ("임원 보수와 직원 수 평균 급여 현황을 알려줘", "executive_compensation"),
    ("회사채 기업어음 단기사채 미상환 잔액을 확인해줘", "debt_securities"),
    ("외부 감사인 감사의견과 감사보수를 조회해줘", "audit_fund"),
    ("연결 재무제표의 매출액 영업이익 현금흐름을 보여줘", "financial_statement"),
    ("대량보유 5% 보고와 임원 지분 변동 공시를 찾아줘", "equity_disclosure"),
    ("유상증자 무상증자와 감자 결정 공시를 찾아줘", "capital_change"),
    ("자기주식 자사주 취득 소각 바이백 공시를 보여줘", "treasury_stock"),
    ("전환사채 CB와 신주인수권부사채 BW 발행 결정을 찾아줘", "convertible_securities"),
    ("회사 합병 인적분할과 주식교환 결정 공시를 찾아줘", "merger_division"),
    ("영업 양도와 유형자산 양수도 결정 공시를 보여줘", "business_transfer"),
    ("해외 증권시장 상장과 ADR GDR 발행 공시를 찾아줘", "overseas_listing"),
    ("타법인 출자와 자회사 지분 취득 처분 공시를 찾아줘", "equity_investment"),
    ("부도 발생 회생절차 소송과 영업정지 공시를 찾아줘", "corporate_issues"),
    ("증권신고서 공모와 증권 발행 등록정보를 확인해줘", "securities_registration"),
]


def test_route_categories_publish_exactly_sixteen_unique_ids() -> None:
    category_ids = [category["id"] for category in ROUTE_CATEGORIES]

    assert len(category_ids) == 16
    assert len(set(category_ids)) == 16
    assert set(category_ids) == EXPECTED_CATEGORY_IDS


@pytest.mark.parametrize(("query", "expected_category"), STRONG_KOREAN_QUERIES)
def test_strong_korean_query_selects_expected_top_category(
    query: str, expected_category: str
) -> None:
    result = classify_disclosure_request(query)

    assert result["routes"][0]["category"] == expected_category


def test_classifier_returns_public_response_shape() -> None:
    query = "최근 공시 검색"

    result = classify_disclosure_request(query, top_k=3)

    assert result["query"] == query
    assert result["total_categories"] == 16
    assert len(result["routes"]) == 3
    assert all(
        set(route) == {
            "category",
            "label_ko",
            "score",
            "matched_terms",
            "supported_tools",
        }
        for route in result["routes"]
    )


@pytest.mark.parametrize("query", ["", "   ", "\n\t"])
def test_classifier_rejects_empty_or_whitespace_query(query: str) -> None:
    with pytest.raises(ValueError, match="query"):
        classify_disclosure_request(query)


@pytest.mark.parametrize("top_k", [0, 17])
def test_classifier_rejects_top_k_outside_category_bounds(top_k: int) -> None:
    with pytest.raises(ValueError, match="top_k"):
        classify_disclosure_request("재무제표 조회", top_k=top_k)


def test_classifier_honors_top_k_at_supported_bounds() -> None:
    assert len(classify_disclosure_request("공시 검색", top_k=1)["routes"]) == 1
    assert len(classify_disclosure_request("공시 검색", top_k=16)["routes"]) == 16


def test_classifier_is_deterministic_for_identical_input() -> None:
    first = classify_disclosure_request("연결 재무제표 매출 영업이익", top_k=5)
    second = classify_disclosure_request("연결 재무제표 매출 영업이익", top_k=5)

    assert first == second


def test_routes_are_ranked_by_nonincreasing_score() -> None:
    routes = classify_disclosure_request("배당금과 최대주주 지분율", top_k=16)["routes"]

    scores = [route["score"] for route in routes]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.parametrize(
    ("query", "expected_tools"),
    [
        (
            "기업 개황과 최근 공시 검색",
            {"get_company_profile", "search_disclosures"},
        ),
        (
            "배당금과 최대주주 지분율",
            {"get_dividend_information", "get_major_shareholders"},
        ),
        ("연결 재무제표 매출액", {"get_financial_statement"}),
        ("직원 수와 평균 급여", {"get_employee_statistics"}),
    ],
)
def test_implemented_domains_publish_their_supported_tools(
    query: str, expected_tools: set[str]
) -> None:
    top_route = classify_disclosure_request(query, top_k=1)["routes"][0]

    assert set(top_route["supported_tools"]) == expected_tools
