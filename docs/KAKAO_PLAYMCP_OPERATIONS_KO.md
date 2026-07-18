# 카카오 PlayMCP 등록·갱신 운영 핸드북

마지막 확인: **2026-07-18 KST**. 이 문서는 `Disclosure Compass(공시나침반)`의
16개 전문 MCP 서버와 82개 OpenDART 도구를 PlayMCP에 등록·갱신하는 실행 기준이다.
코드 배포(공개 URL을 운영하는 일)와 PlayMCP 등록(그 URL을 심사·노출하는 일)은
서로 다른 단계다.

## 1. 확정된 PlayMCP 제약

제공받은 [PlayMCP 서버 개발가이드](https://app.notion.com/p/PlayMCP-2d89b97b4888808a9e1dc17a13e70187)
(2026-06-12 업데이트)를 기준으로 한다.

| 항목 | 요구 사항 | 이 저장소의 대응 |
| --- | --- | --- |
| 전송 방식 | 외부에서 접근 가능한 Streamable HTTP MCP | HTTPS 공개 호스트의 `/specialists/<id>/mcp` |
| 프로토콜 | MCP 2025-03-26 이상, 2025-11-25 이하 | FastMCP 2.14.5 Streamable HTTP |
| 도구 수 | MCP 서버당 최대 20개, 권장 3-10개 | 16개 서버에 2-9개씩, 합계 82개 |
| 도구 이름 | 1-128자, 영문·숫자·`_`·`-`, 중복 불가 | 기존 `dart_*` 이름 유지, 서버별 중복 없음 |
| 도구 메타데이터 | name, description, inputSchema, annotations 필수 | 모든 도구에 입력 스키마와 4개 읽기 전용 annotation |
| 설명 | 영문 권장, 서비스 정식 영문/한글명 포함 | `Disclosure Compass(공시나침반)`, `OpenDART (전자공시시스템 DART)` 포함 |
| 응답 성능 | p99 3,000ms 이내 | OpenDART 호출 시간·실패율을 운영에서 측정해야 함 |

따라서 82개를 하나의 `tools/list`에 넣는 v1.1.0 방식은 **도구 수 제한 위반**이다.
v1.2.0은 16개 공개 MCP endpoint로 분할한다. 기존 10개 gateway endpoint는
호환성을 위한 별도 MCP이며, 82개 전문 도구 등록 수에는 포함하지 않는다.

## 2. 현재 실제 PlayMCP 콘솔 상태

실제 개발자 콘솔은 [playmcp.kakao.com/console](https://playmcp.kakao.com/console?tab=registered)이다.
2026-07-18 로그인 상태에서 확인한 값은 다음과 같다.

| 콘솔 항목 | 관측값 |
| --- | --- |
| 등록된 MCP | 1개 |
| 임시 등록된 MCP | 0개 |
| 기존 MCP | `Disclosure Compass(공시나침반)` |
| 기존 MCP 식별자 | `dartcompass` |
| 심사 상태 | 심사 완료 |
| 연결 상태 | Online |
| 콘솔 표시 도구 수 | 6개 |
| 현재 endpoint | `https://disclosure-compass.playmcp-endpoint.kakaocloud.io/mcp` |
| 신규 등록 | `새로운 MCP 서버 등록` 버튼 사용 가능 |

같은 시각에 원격 endpoint를 MCP Client로 직접 조회하면 `tools/list`은 gateway 도구
10개를 반환한다. 즉 콘솔 카드의 `Tools 6`은 최신 원격 목록과 일치하지 않으며,
도움말의 “상세 도구 정보는 자동 갱신되지 않는다”는 설명과도 일치한다. 등록 수의
판정은 콘솔 카드가 아니라 `정보 불러오기` 및 원격 `tools/list`로 한다.

신규 등록 화면은 팀프로필, 대표 이미지, MCP 이름, MCP 식별자(영문·숫자, 최대 16자),
설명, 대화 예시, 인증 방식, MCP Endpoint를 입력한 뒤 **정보 불러오기**로 원격
`tools/list`을 확인하고 `등록 및 심사 요청` 또는 `임시 등록`을 선택하는 흐름이다.

기존 MCP를 바꿀 때는 [도구 정보 갱신 도움말](https://app.notion.com/p/MCP-2389b97b488880b3896bceb076899938)에
따라 카드 메뉴의 `수정`을 열고 **정보 불러오기 → 저장하기 또는 등록 및 심사 요청**을
수행한다. 상세 화면의 도구 정보는 자동 갱신되지 않지만, AI 채팅 호출은 최신 원격
도구 정보를 사용한다.

## 3. 배포해야 하는 endpoint 목록

공개 호스트 기준 URL은 `https://<PUBLIC_MCP_BASE_URL>`로 표기한다. 실제 배포 후
16개 URL 모두가 공개 HTTPS여야 한다.

| domain ID | PlayMCP 식별자 제안 | 표시 이름 제안 | 도구 수 | 등록 endpoint |
| --- | --- | --- | ---: | --- |
| `disclosure_search` | `dartSearch` | 공시나침반 공시 검색 | 4 | `/specialists/disclosure_search/mcp` |
| `shareholder_stock` | `dartHolder` | 공시나침반 주주·주식 | 8 | `/specialists/shareholder_stock/mcp` |
| `executive_compensation` | `dartExec` | 공시나침반 임원·보수 | 9 | `/specialists/executive_compensation/mcp` |
| `debt_securities` | `dartDebt` | 공시나침반 채무증권 | 6 | `/specialists/debt_securities/mcp` |
| `audit_fund` | `dartAudit` | 공시나침반 감사·자금 | 5 | `/specialists/audit_fund/mcp` |
| `financial_statement` | `dartFinance` | 공시나침반 재무정보 | 7 | `/specialists/financial_statement/mcp` |
| `equity_disclosure` | `dartEquity` | 공시나침반 지분공시 | 2 | `/specialists/equity_disclosure/mcp` |
| `securities_registration` | `dartReg` | 공시나침반 증권등록 | 6 | `/specialists/securities_registration/mcp` |
| `capital_change` | `dartCapital` | 공시나침반 증자·감자 | 4 | `/specialists/capital_change/mcp` |
| `treasury_stock` | `dartTreasury` | 공시나침반 자기주식 | 4 | `/specialists/treasury_stock/mcp` |
| `convertible_securities` | `dartConvert` | 공시나침반 전환증권 | 4 | `/specialists/convertible_securities/mcp` |
| `merger_division` | `dartMerger` | 공시나침반 합병·분할 | 4 | `/specialists/merger_division/mcp` |
| `business_transfer` | `dartTransfer` | 공시나침반 영업·자산 양수도 | 5 | `/specialists/business_transfer/mcp` |
| `overseas_listing` | `dartOverseas` | 공시나침반 해외상장 | 4 | `/specialists/overseas_listing/mcp` |
| `equity_investment` | `dartInvestment` | 공시나침반 지분거래 | 3 | `/specialists/equity_investment/mcp` |
| `corporate_issues` | `dartIssues` | 공시나침반 기업이슈 | 7 | `/specialists/corporate_issues/mcp` |

MCP 식별자는 PlayMCP가 도구명 앞에 붙이는 prefix이므로 서로 달라야 한다. 이름이나
식별자에 `kakao`를 넣지 않는다. 각 등록에 `assets/disclosure-compass.png`를 대표
이미지로 재사용할 수 있다.

## 4. 코드 배포 후 등록 절차

1. v1.2.0을 공개 컨테이너 호스트에 배포한다. `DART_API_KEY`는 호스트의 런타임
   secret으로만 주입한다. GitHub, 이미지, PlayMCP 설명에 쓰지 않는다.
2. 아래 검증을 통과한 **실제 URL**만 등록한다.
3. 콘솔에서 `새로운 MCP 서버 등록`을 열고 위 표의 한 행을 입력한다.
4. Endpoint에 `https://<host>/specialists/<domain-id>/mcp`를 입력하고
   `정보 불러오기`를 누른다. 그 서버의 도구 수와 이름이 표·소스와 정확히 같아야 한다.
5. 16개를 우선 `임시 등록`으로 연결 검증한 뒤, 이상 없으면 각각 `등록 및 심사 요청`한다.
6. 기존 심사 완료 MCP는 수정 화면에서 endpoint를 v1.2.0 호스트의 `/mcp`로 유지하거나
   교체한 뒤 정보 불러오기를 실행한다. 이 gateway는 10개 도구이므로 제한을 만족한다.
7. 심사 완료 후 콘솔 카드의 각 도구 수 합계가 82개인지 확인하고, AI 채팅에서 대표
   16개 도메인을 한 번씩 호출한다.

콘솔은 원격 URL을 등록·검증하는 서비스다. 현재 작업공간의 Dockerfile을 공개 URL로
실행하는 별도 호스트의 재배포 권한과 `DART_API_KEY` secret이 반드시 필요하다.

## 5. 배포 전·후 검증

```bash
PUBLIC_MCP_BASE_URL='https://your-public-host.example'

.venv/bin/python - <<'PY'
import asyncio
import os

from fastmcp import Client
from opendart_mcp.specialists import SPECIALIST_TOOLS, specialist_mcp_path


async def main() -> None:
    base = os.environ["PUBLIC_MCP_BASE_URL"].rstrip("/")
    total = 0
    for server_id, specs in SPECIALIST_TOOLS.items():
        async with Client(base + specialist_mcp_path(server_id)) as client:
            tools = await client.list_tools()
        names = {tool.name for tool in tools}
        assert names == {spec.name for spec in specs}, server_id
        assert 1 <= len(tools) <= 20, server_id
        total += len(tools)
    assert total == 82
    print(f"verified specialist servers={len(SPECIALIST_TOOLS)}, tools={total}")


asyncio.run(main())
PY
```

추가로 `GET /health`가 200인지, 대표 endpoint가 실제 OpenDART 데이터를 `status=ok`로
반환하는지, p99 호출 시간이 3초 이내인지 확인한다. 테스트에만 API 키를 넣지 말고
배포 런타임의 secret을 사용한다.

## 6. 관련 문서

- [PlayMCP 서버 개발가이드](https://app.notion.com/p/PlayMCP-2d89b97b4888808a9e1dc17a13e70187)
- [서비스 도움말](https://app.notion.com/p/2189b97b4888803dbbdcef264e7eff58)
- [MCP 도구 정보 갱신 도움말](https://app.notion.com/p/MCP-2389b97b488880b3896bceb076899938)
- [MCP 전체 공개 도움말](https://app.notion.com/p/MCP-2189b97b488880d3b10acaa332e79c4e?pvs=25)
- [구현·배포 기록](IMPLEMENTATION_DEPLOYMENT_KO.md)
- [README](../README.md)

## 7. 상태 기록

- `f9ab137` / v1.1.0: 82개를 하나의 MCP endpoint에 직접 등록하려던 후보. PlayMCP
  서버당 최대 20개 제한을 확인한 뒤 배포 대상으로 사용하지 않는다.
- v1.2.0: 16개 전문 FastMCP를 하나의 ASGI 컨테이너의 16개 Streamable HTTP URL로
  마운트한다. 로컬 HTTP 검증은 gateway 10개, 전문 서버 16개, 전문 도구 82개를 확인했다.
- 아직 이 v1.2.0 컨테이너를 공개 호스트에 올린 검증 URL은 없다. 따라서 지금 콘솔에
  16개를 심사 요청하면 안 되며, 공개 호스팅 배포가 다음 필수 단계다.
