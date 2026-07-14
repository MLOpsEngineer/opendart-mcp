# Disclosure Compass (공시나침반)

A focused Model Context Protocol server for public company disclosures from
[OpenDART (전자공시시스템 DART)](https://opendart.fss.or.kr/). Disclosure
Compass (공시나침반) exposes seven read-only tools over Streamable HTTP and
returns concise, normalized JSON.

This project is independent open-source software and is not an official
OpenDART product.

## Tools

| Tool | Purpose |
| --- | --- |
| `get_company_profile` | Basic company and listing information |
| `search_disclosures` | Disclosure filings in a bounded date range |
| `get_financial_statement` | A bounded set of statement accounts |
| `get_dividend_information` | Current and prior-period dividend rows |
| `get_major_shareholders` | Major shareholder positions |
| `get_employee_statistics` | Employee counts, tenure, and pay statistics |
| `classify_disclosure_request` | Rank a Korean request across 16 disclosure domains without executing a disclosure query |

All tools are declared read-only, non-destructive, idempotent, and open-world.
Every list response is capped at 50 normalized rows; disclosure search is capped
at 20 rows. Upstream calls use strict connect/read timeouts and reject responses
larger than 2 MB.

## Disclosure request classification

`classify_disclosure_request` maps a non-empty Korean natural-language request
of up to 500 characters to the most relevant OpenDART disclosure domains.
`top_k` defaults to 3 and may be set from 1 through 16. The response contains
the original `query`, `total_categories`, and score-ranked `routes`. Each route
contains:

- `category`: the stable domain ID
- `label_ko`: the Korean domain label
- `score`: the normalized relevance score
- `matched_terms`: terms from the request that contributed to the route
- `supported_tools`: data tools currently exposed by this server for the domain

This tool performs deterministic term matching and classifies only. It does not
call OpenDART, execute the returned data tools, or run 16 separate MCP servers.
`supported_tools` names only the current data tools that may help with a route;
it does not indicate a dedicated backend for each category.

The classifier recognizes exactly these 16 domains:

| Category | Korean label |
| --- | --- |
| `disclosure_search` | 공시검색/기업개황 |
| `shareholder_stock` | 주주/주식 정보 |
| `executive_compensation` | 임원/보수 정보 |
| `debt_securities` | 채무증권 정보 |
| `audit_fund` | 감사/자금 정보 |
| `financial_statement` | 재무정보 |
| `equity_disclosure` | 지분공시 |
| `capital_change` | 증자감자 |
| `treasury_stock` | 자기주식 |
| `convertible_securities` | 전환증권 |
| `merger_division` | 합병분할 |
| `business_transfer` | 영업/자산 양수도 |
| `overseas_listing` | 해외상장 |
| `equity_investment` | 지분거래 |
| `corporate_issues` | 기업이슈 |
| `securities_registration` | 증권발행/등록정보 |

Example request:

```json
{
  "query": "연결 재무제표 매출액",
  "top_k": 1
}
```

Example response:

```json
{
  "query": "연결 재무제표 매출액",
  "routes": [
    {
      "category": "financial_statement",
      "label_ko": "재무정보",
      "score": 1.0,
      "matched_terms": ["연결 재무제표", "재무제표", "매출액"],
      "supported_tools": ["get_financial_statement"]
    }
  ],
  "total_categories": 16
}
```

Use `get_financial_statement` in a separate MCP call when the request includes
its required company and reporting-period arguments.

## Requirements

- Python 3.11-3.13
- An OpenDART API key from <https://opendart.fss.or.kr/>

## Run locally

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
export DART_API_KEY='your-runtime-secret'
opendart-mcp
```

The MCP endpoint is `http://localhost:8000/mcp` and the health endpoint is
`http://localhost:8000/health`. Set `PORT` to override port 8000.

The `corp_code` arguments are OpenDART eight-digit company identifiers, not
six-digit stock codes. For example, OpenDART's public guide uses `00126380` for
Samsung Electronics.

## Docker / PlayMCP deployment

The image is compatible with Linux AMD64 and runs as a non-root user.

```bash
docker build --platform linux/amd64 -t opendart-mcp .
docker run --rm -p 8000:8000 \
  -e DART_API_KEY='your-runtime-secret' \
  opendart-mcp
```

Configure the deployment secret as `DART_API_KEY`; never bake it into the image
or commit it. Register `/mcp` as the Streamable HTTP endpoint. The server uses
stateless HTTP so it does not require session affinity.

## Development checks

```bash
ruff check .
pytest -q
python -m compileall -q src tests
```

Tests use local fixtures and never call OpenDART or require an API key.

## Data and operational notes

- Results are public disclosure data, but users should confirm material facts in
  the original filing before making decisions.
- OpenDART may update data between otherwise identical calls.
- The server does not store query inputs or results.
- Upstream rate limits and maintenance windows still apply.

## License

MIT. See [LICENSE](LICENSE).
