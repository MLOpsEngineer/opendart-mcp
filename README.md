# Disclosure Compass (공시나침반)

A focused Model Context Protocol server for public company disclosures from
[OpenDART (전자공시시스템 DART)](https://opendart.fss.or.kr/). Disclosure
Compass (공시나침반) exposes **92 read-only tools** over Streamable HTTP:
ten convenience gateway tools plus all 82 original OpenDART specialist tools.
The specialist tools retain their 16 disclosure-domain identities while sharing
one deployable MCP endpoint, without LLM, vector-search, or A2A runtime
dependencies.

This project is independent open-source software and is not an official
OpenDART product.

For the complete 16-domain/82-tool catalog and the Korean PlayMCP deployment
runbook, see [구현·배포 운영 기록](docs/IMPLEMENTATION_DEPLOYMENT_KO.md) and
[카카오 PlayMCP 운영·갱신 핸드북](docs/KAKAO_PLAYMCP_OPERATIONS_KO.md).

## Tools

### Gateway tools (10)

| Tool | Purpose |
| --- | --- |
| `get_company_profile` | Basic company and listing information |
| `search_disclosures` | Disclosure filings in a bounded date range |
| `get_financial_statement` | A bounded set of statement accounts |
| `get_dividend_information` | Current and prior-period dividend rows |
| `get_major_shareholders` | Major shareholder positions |
| `get_employee_statistics` | Employee counts, tenure, and pay statistics |
| `classify_disclosure_request` | Rank a Korean request across 16 disclosure domains and show their specialist tools |
| `list_disclosure_servers` | Inspect all 16 specialist servers and 82 tool names/endpoints |
| `call_disclosure_server_tool` | Execute an exact named tool on an exact specialist server |
| `route_and_call_disclosure` | Classify, select a specialist tool, and execute it in one call |

### Specialist tools (82)

Every original `dart_*` tool is also directly published in `tools/list`.
The tools are grouped by the same 16 domain IDs as the classifier and preserve
the original OpenDART endpoint names; the full per-domain catalog is in the
[implementation record](docs/IMPLEMENTATION_DEPLOYMENT_KO.md#4-전문-서버-16개와-내부-tool-82개).

Specialist tools take one `arguments` object. Its accepted fields depend on the
endpoint and include `corp_code` or `corp_name`, `business_year`, `report_code`,
`begin_date`, `end_date`, `corp_codes`, `receipt_number`, `fs_division`,
`statement_type`, `index_code`, and `max_items`. For example:

```json
{
  "arguments": {
    "corp_code": "00126380",
    "begin_date": "20250101",
    "end_date": "20251231",
    "max_items": 10
  }
}
```

All tools are declared read-only, non-destructive, idempotent, and open-world.
Every specialist result is capped at 50 rows. Binary filing and XBRL tools
return bounded ZIP metadata rather than raw file contents. Upstream calls use
strict connect/read timeouts and reject JSON responses larger than 2 MB or
binary responses larger than 8 MB.

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
- `specialist_tools`: original tool names available on that domain's MCP server

This classifier performs deterministic term matching and does not itself call
OpenDART. Use `route_and_call_disclosure` to classify and execute in one request,
or use `call_disclosure_server_tool` for deterministic server/tool selection.
The 16 specialist servers are real FastMCP instances called through in-memory
FastMCP clients; they are not 16 separately deployed network services.

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
      "supported_tools": ["get_financial_statement"],
      "specialist_tools": [
        "dart_fnlttSinglAcnt",
        "dart_fnlttMultiAcnt",
        "dart_fnlttXbrl",
        "dart_fnlttSinglAcntAll",
        "dart_xbrlTaxonomy",
        "dart_fnlttSinglIndx",
        "dart_fnlttCmpnyIndx"
      ]
    }
  ],
  "total_categories": 16
}
```

To execute a routed request directly, pass a company identifier and any
period-specific fields to `route_and_call_disclosure`:

```json
{
  "query": "삼성전자 전환사채 발행 결정을 찾아줘",
  "corp_code": "00126380",
  "begin_date": "20250101",
  "end_date": "20251231"
}
```

This selects the `convertible_securities` server and its
`dart_cvbdIsDecsn` tool. Callers that already know the exact target can instead
use `call_disclosure_server_tool` with `server_id`, `tool_name`, and an
`arguments` object. Accepted fields depend on the endpoint and include
`corp_code` or `corp_name`, `business_year`, `report_code`, `begin_date`,
`end_date`, `corp_codes`, `receipt_number`, `fs_division`, `statement_type`,
`index_code`, and `max_items`.

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
stateless HTTP so it does not require session affinity. Verify that PlayMCP
discovers 92 tools after deployment: ten gateway tools and 82 `dart_*`
specialist tools.

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
