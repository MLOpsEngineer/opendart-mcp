# Disclosure Compass (공시나침반)

A focused Model Context Protocol server for public company disclosures from
[OpenDART (전자공시시스템 DART)](https://opendart.fss.or.kr/). Disclosure
Compass (공시나침반) exposes six read-only tools over Streamable HTTP and
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

All tools are declared read-only, non-destructive, idempotent, and open-world.
Every list response is capped at 50 normalized rows; disclosure search is capped
at 20 rows. Upstream calls use strict connect/read timeouts and reject responses
larger than 2 MB.

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
