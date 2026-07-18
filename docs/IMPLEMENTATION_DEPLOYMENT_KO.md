# Disclosure Compass 구현·배포 운영 기록

이 문서는 기존 OpenDART MCP 구현을 공모전 제출용 공개 서버로 정리한 작업 내용과
현재 배포 상태, 검증 방법, 재배포 시 주의사항을 기록한다. 공개 프로젝트 설명에는
개발자의 소속 회사명을 사용하지 않았다.

## 1. 현재 배포 상태

상태 확인 시각: **2026-07-15 08:21:52 KST**

| 항목 | 현재 값 |
| --- | --- |
| 운영 판정 | 정상(Operational) |
| PlayMCP 서버 이름 | `disclosure-compass` |
| PlayMCP 서버 ID | `3506` |
| MCP 엔드포인트 | `https://disclosure-compass.playmcp-endpoint.kakaocloud.io/mcp` |
| 배포 소스 | `https://github.com/MLOpsEngineer/opendart-mcp.git` |
| 배포 브랜치 | `main` |
| 배포 커밋 | `2f1a11175ea2fe6537da5fb1bfac80d0e8f426ad` |
| 외부 공개 Tool | 10개 |
| 내부 전문 MCP 서버 | 16개 |
| 내부 OpenDART Tool | 82개 |
| 컨테이너 포트 | `8000` |
| 런타임 시크릿 이름 | `DART_API_KEY` |

현재 운영 판정은 PlayMCP 엔드포인트에 FastMCP 클라이언트로 직접 접속하여 내린
것이다. MCP 초기화와 `list_tools`가 성공했고, 인벤토리 및 실제 OpenDART 호출까지
정상 응답했다.

확인 결과:

- 공개 Tool 목록: 10개 반환
- `list_disclosure_servers`: `server_count=16`, `tool_count=82`
- 자연어 요청 `전환사채 발행 결정을 찾아줘`:
  `convertible_securities/dart_cvbdIsDecsn`으로 라우팅
- 라우팅된 OpenDART 엔드포인트: `cvbdIsDecsn.json`, `status=ok`
- 명시 호출 `audit_fund/dart_accnutAdtorNmNdAdtOpinion`:
  `accnutAdtorNmNdAdtOpinion.json`, `status=ok`, 3건 반환

배포 완료 시 PlayMCP 관리 화면에서도 `Status Active`와 10개 Tool 등록을 확인했다.
이번 상태 점검 시점에는 Mac이 잠겨 관리 화면을 다시 읽을 수 없었으므로, 위의 현재
운영 판정은 관리 화면 문구가 아니라 실제 원격 MCP 프로토콜 응답을 기준으로 한다.

## 2. 목표와 최종 구조

기존 구현에 있던 16개 업무 도메인과 82개 OpenDART Tool을 유지하면서, 공모전에서
사용하기 쉬운 단일 Streamable HTTP MCP 서버로 배포하는 것이 목표였다. LLM,
벡터 검색, A2A 런타임 같은 비공개·고비용 의존성은 제거하고 결정적 분류기와
FastMCP 인메모리 호출 구조로 바꿨다.

```mermaid
flowchart LR
    A["MCP 클라이언트"] --> B["공개 Streamable HTTP MCP\n10개 Gateway Tool"]
    B --> C["결정적 요청 분류기"]
    B --> D["정확한 서버·Tool 지정 호출"]
    C --> E["SpecialistServerRegistry"]
    D --> E
    E --> F["16개 인프로세스 FastMCP 서버\n82개 Tool"]
    F --> G["OpenDART 공식 API"]
```

16개 서버는 각각 독립적인 FastMCP 인스턴스이지만 별도 컨테이너나 별도 네트워크
서비스로 배포되지 않는다. 하나의 프로세스 안에서 FastMCP `Client`를 통해 호출된다.
외부에는 사용성이 높은 10개 Gateway Tool만 노출한다.

## 3. 외부 공개 Gateway Tool 10개

| Tool | 역할 |
| --- | --- |
| `get_company_profile` | 기업 개황과 상장 정보 조회 |
| `search_disclosures` | 제한된 기간의 공시 검색 |
| `classify_disclosure_request` | 한국어 요청을 16개 도메인으로 분류 |
| `list_disclosure_servers` | 16개 서버와 82개 Tool·엔드포인트 조회 |
| `call_disclosure_server_tool` | 지정한 서버의 지정 Tool 실행 |
| `route_and_call_disclosure` | 요청 분류, Tool 선택, 실행을 한 번에 처리 |
| `get_financial_statement` | 재무제표 계정 조회 |
| `get_dividend_information` | 배당 정보 조회 |
| `get_major_shareholders` | 최대주주 정보 조회 |
| `get_employee_statistics` | 직원 수·근속·급여 정보 조회 |

모든 공개 Tool은 `readOnlyHint=true`, `destructiveHint=false`,
`idempotentHint=true`, `openWorldHint=true`로 선언되어 있다.

## 4. 전문 서버 16개와 내부 Tool 82개

아래 목록은 현재 `SPECIALIST_TOOLS` 레지스트리의 실제 구성이다.

1. `disclosure_search` — 4개
   - `dart_list`, `dart_company`, `dart_document`, `dart_corpCode`
2. `shareholder_stock` — 8개
   - `dart_stockTotqySttus`, `dart_irdsSttus`, `dart_alotMatter`,
     `dart_tesstkAcqsDspsSttus`, `dart_hyslrSttus`, `dart_hyslrChgSttus`,
     `dart_mrhlSttus`, `dart_otrCprInvstmntSttus`
3. `executive_compensation` — 9개
   - `dart_exctvSttus`, `dart_empSttus`, `dart_outcmpnyDrctrNdChangeSttus`,
     `dart_hmvAuditIndvdlBySttus`, `dart_hmvAuditAllSttus`, `dart_indvdlByPay`,
     `dart_unrstExctvMendngSttus`, `dart_drctrAdtAllMendngSttusGmtsckConfmAmount`,
     `dart_drctrAdtAllMendngSttusMendngPymntamtTyCl`
4. `debt_securities` — 6개
   - `dart_detScritsIsuAcmslt`, `dart_entrprsBilScritsNrdmpBlce`,
     `dart_srtpdPsndbtNrdmpBlce`, `dart_cprndNrdmpBlce`,
     `dart_newCaplScritsNrdmpBlce`, `dart_cndlCaplScritsNrdmpBlce`
5. `audit_fund` — 5개
   - `dart_accnutAdtorNmNdAdtOpinion`, `dart_adtServcCnclsSttus`,
     `dart_accnutAdtorNonAdtServcCnclsSttus`, `dart_pssrpCptalUseDtls`,
     `dart_prvsrpCptalUseDtls`
6. `financial_statement` — 7개
   - `dart_fnlttSinglAcnt`, `dart_fnlttMultiAcnt`, `dart_fnlttXbrl`,
     `dart_fnlttSinglAcntAll`, `dart_xbrlTaxonomy`, `dart_fnlttSinglIndx`,
     `dart_fnlttCmpnyIndx`
7. `equity_disclosure` — 2개
   - `dart_majorstock`, `dart_elestock`
8. `securities_registration` — 6개
   - `dart_estkRs`, `dart_bdRs`, `dart_stkdpRs`, `dart_mgRs`, `dart_extrRs`,
     `dart_dvRs`
9. `capital_change` — 4개
   - `dart_piicDecsn`, `dart_fricDecsn`, `dart_pifricDecsn`, `dart_crDecsn`
10. `treasury_stock` — 4개
    - `dart_tsstkAqDecsn`, `dart_tsstkDpDecsn`, `dart_tsstkAqTrctrCnsDecsn`,
      `dart_tsstkAqTrctrCcDecsn`
11. `convertible_securities` — 4개
    - `dart_cvbdIsDecsn`, `dart_bdwtIsDecsn`, `dart_exbdIsDecsn`,
      `dart_wdCocobdIsDecsn`
12. `merger_division` — 4개
    - `dart_cmpMgDecsn`, `dart_cmpDvDecsn`, `dart_cmpDvmgDecsn`,
      `dart_stkExtrDecsn`
13. `business_transfer` — 5개
    - `dart_bsnInhDecsn`, `dart_bsnTrfDecsn`, `dart_tgastInhDecsn`,
      `dart_tgastTrfDecsn`, `dart_stkrtbdInhDecsn`
14. `overseas_listing` — 4개
    - `dart_ovLstDecsn`, `dart_ovDlstDecsn`, `dart_ovLst`, `dart_ovDlst`
15. `equity_investment` — 3개
    - `dart_otcprStkInvscr`, `dart_otcprStkInvscrInhDecsn`,
      `dart_otcprStkInvscrTrfDecsn`
16. `corporate_issues` — 7개
    - `dart_bnkMngtPcbg`, `dart_dsRsOcr`, `dart_dfOcr`, `dart_bsnSp`,
      `dart_ctrcvsBgrq`, `dart_rhbPcEnd`, `dart_lwstLg`

합계는 **16개 서버, 82개 Tool**이다.

## 5. 구현 내용

### `src/opendart_mcp/specialists.py`

- 원본 Tool 이름, OpenDART 엔드포인트, 한국어 라벨, 선택 키워드를 정적 레지스트리로
  정의했다.
- 시작 시 16개 FastMCP 전문 서버를 인프로세스로 생성한다.
- `SpecialistServerRegistry.call_tool`이 FastMCP `Client`를 통해 실제 Tool을 호출한다.
- 기업코드, 사업연도, 보고서 코드, 날짜, 재무제표 구분 등 엔드포인트별 인자를
  검증·정규화한다.
- 문서·XBRL ZIP 응답은 원문 전체 대신 파일명, 크기, SHA-256 등의 제한된 메타데이터만
  반환한다.

### `src/opendart_mcp/routing.py`

- 16개 도메인별 한국어 키워드와 공개 Gateway Tool 연결을 정의했다.
- 공백과 대소문자를 정규화하고, 더 길고 구체적인 문구에 높은 점수를 부여한다.
- 동일 입력에는 동일한 결과를 내는 결정적 분류기이며 외부 LLM을 호출하지 않는다.
- 분류 결과에 공개 Tool과 해당 전문 서버의 원본 Tool 목록을 함께 제공한다.

### `src/opendart_mcp/server.py`

- 외부 공개 Tool을 7개에서 10개로 확장했다.
- `list_disclosure_servers`, `call_disclosure_server_tool`,
  `route_and_call_disclosure`를 추가했다.
- 단일 Streamable HTTP 엔드포인트에서 분류, 명시 호출, 자동 라우팅 호출을 모두
  지원한다.
- `/health` 라우트를 제공하고 stateless HTTP 모드로 실행한다.

### `src/opendart_mcp/client.py`

- `DART_API_KEY`를 런타임 환경에서만 읽는다.
- JSON 응답은 2 MB, 바이너리 응답은 8 MB로 제한한다.
- JSON 요청은 10초, 바이너리 요청은 20초의 읽기 제한 시간을 사용한다.
- OpenDART 기업코드 ZIP을 파싱하고 프로세스 메모리에 캐시하여 회사명으로
  `corp_code`를 찾을 수 있게 했다.
- 요청·응답·API 키를 디스크에 저장하지 않는다.

### `Dockerfile`과 패키징

- Python 3.12 slim 이미지를 사용한다.
- Linux AMD64에서 동작하며 비루트 `app` 사용자로 실행한다.
- 기본 포트는 8000이고 `/health`를 컨테이너 헬스체크에 사용한다.
- `fastmcp==2.14.5`, `httpx==0.28.1`로 런타임 의존성을 고정했다.

## 6. 안전성 경계

- 모든 작업은 공시 데이터 읽기 전용이다.
- 전문 Tool 결과는 최대 50개 행으로 제한한다.
- 공시 검색 Gateway 결과는 최대 20개 행으로 제한한다.
- 날짜 범위, 기업코드, 보고서 코드, 재무제표 구분을 사전에 검증한다.
- OpenDART 오류 코드와 네트워크 오류는 MCP Tool 오류로 변환한다.
- API 키는 저장소나 이미지에 포함하지 않고 PlayMCP 시크릿으로만 주입한다.
- 원본 공시 문서와 XBRL 바이너리는 그대로 외부에 전달하지 않는다.

## 7. 테스트와 검증

구현 커밋에서 수행한 로컬 검증:

```text
pytest: 144 passed
ruff: passed
compileall: passed
전문 서버 등록: 16/16
전문 Tool 어댑터 실행: 82/82
원본 서버·Tool·엔드포인트 카탈로그 비교: 누락 0, 추가 0, 불일치 0
```

테스트의 주요 보장 범위:

- 공개 Tool이 정확히 10개이며 읽기 전용 annotation을 갖는지 확인
- 라우팅 카테고리가 정확히 16개인지 확인
- 각 전문 서버가 자신의 전체 Tool을 FastMCP에 등록하는지 확인
- 82개 모든 Tool 어댑터가 지정 엔드포인트를 실행하는지 확인
- 기업코드 ZIP 파싱·캐시와 바이너리 메타데이터 처리 확인
- 잘못된 서버, Tool, 기업코드, 날짜, 보고서 코드 거부 확인
- `/health` 응답 확인

현재 원격 검증에 사용한 최소 예제:

```python
import asyncio

from fastmcp import Client

URL = "https://disclosure-compass.playmcp-endpoint.kakaocloud.io/mcp"


async def main() -> None:
    async with Client(URL) as client:
        tools = await client.list_tools()
        assert len(tools) == 10

        inventory = (await client.call_tool("list_disclosure_servers", {})).data
        assert inventory["server_count"] == 16
        assert inventory["tool_count"] == 82


asyncio.run(main())
```

저장소 전체 검증 명령:

```bash
.venv/bin/ruff check .
.venv/bin/pytest -q
.venv/bin/python -m compileall -q src tests
```

## 8. PlayMCP 배포 설정

현재 배포에 사용한 값:

| 설정 | 값 |
| --- | --- |
| 방식 | Git 소스 빌드 |
| 서버 이름 | `disclosure-compass` |
| 설명 | 소속 회사 표기 없는 영문 OpenDART MCP 설명 |
| Git URL | `https://github.com/MLOpsEngineer/opendart-mcp.git` |
| Branch / ref | `main` |
| Dockerfile | `Dockerfile` |
| PAT | 미사용(공개 저장소) |
| Secret key | `DART_API_KEY` |
| Container port | `8000` |

재배포 전에는 다음을 확인한다.

1. `main`에 배포 대상 커밋이 push되어 있는지 확인한다.
2. 로컬에서 ruff, pytest, compileall을 통과시킨다.
3. 16개 서버와 82개 Tool 카탈로그 수가 바뀌지 않았는지 확인한다.
4. PlayMCP 시크릿 `DART_API_KEY`가 등록되어 있는지 확인한다.
5. 배포 후 관리 화면의 `Active`와 외부 Tool 10개를 확인한다.
6. 실제 엔드포인트에서 `list_tools`, 인벤토리, 대표 OpenDART 호출을 실행한다.

## 9. 알려진 제한과 운영 주의사항

- 분류기는 키워드 기반 결정적 라우터다. 임의의 복잡한 표현을 LLM처럼 의미적으로
  해석하지 않는다. 필요하면 정확한 `server_id`와 `tool_name`을 지정한다.
- 16개 전문 서버는 한 프로세스 안에서 실행되므로 개별 서버만 독립 확장하거나
  독립 배포하는 구조는 아니다.
- OpenDART의 호출 제한, 점검 시간, 데이터 갱신 상태에 영향을 받는다.
- 정상 요청이라도 해당 기간에 데이터가 없으면 `status=ok`, `count=0`이 가능하다.
- 로컬 Docker 데몬이 응답하지 않아 로컬 이미지 빌드는 실행하지 못했다. 대신
  PlayMCP 클라우드 빌드 성공, `Active` 전환, 원격 MCP 호출 성공으로 실제 배포
  이미지를 검증했다.
- 로컬 FastMCP 클라이언트 실행 시 Authlib의 deprecated API 경고가 출력되지만 현재
  연결이나 Tool 실행에는 영향을 주지 않는다. 서버 오류와 혼동하지 않는다.

## 10. 변경 기록

핵심 구현 커밋:

```text
2f1a111 Execute every disclosure domain through specialist MCP tools
```

이 커밋은 16개 전문 FastMCP 서버, 82개 Tool 어댑터, 3개 Gateway Tool,
OpenDART 바이너리·기업코드 처리, 관련 테스트와 공개 문서를 추가했다.

## 11. PlayMCP 운영·갱신 기준

2026-07-18 원격 재검증과 본선 대응 절차, 그리고 “외부 공개 10개”와
“내부 전문 82개”의 차이는
[카카오 PlayMCP 운영·갱신 핸드북](KAKAO_PLAYMCP_OPERATIONS_KO.md)을 기준으로 한다.
특히 `tools/list`에 약 80개 도구가 직접 보여야 하는 요구라면, 이 문서의
현재 Gateway 구조만 재배포해서는 충족되지 않는다.

## 12. v1.1.0 — 82개 전문 Tool 직접 공개

2026-07-18에 본선 요구에 맞춰 공개 MCP 표면을 확장했다. 기존 Gateway 10개는
호환성을 위해 유지하고, `SPECIALIST_TOOLS`의 16개 도메인·82개 명세를 최상위
`tools/list`에도 개별 도구로 등록한다. 따라서 v1.1.0의 기대 공개 Tool 수는
**92개(10 Gateway + 82 전문 Tool)**다.

- `src/opendart_mcp/server.py`의 `_register_public_specialist_tools`가 각 명세를
  원본 `dart_*` 이름으로 등록한다.
- 각 공개 전문 Tool은 해당 `server_id`를 설명과 FastMCP tag로 보존하지만, MCP
  프로토콜의 도구 목록은 평면이므로 카카오에는 하나의 endpoint의 82개 도구로
  나타난다. 16개를 별도 endpoint로 배포하는 변경은 하지 않았다.
- 각 Tool은 `arguments` 객체 하나를 받고 현재
  `SpecialistServerRegistry.call_tool`을 통해 동일한 검증·행 제한·OpenDART
  어댑터를 사용한다.
- 모든 도구의 `readOnlyHint=true`, `destructiveHint=false`,
  `idempotentHint=true`, `openWorldHint=true` annotation을 유지한다.
- `tests/test_server.py`는 92개 전체 목록과 82개 공개 wrapper의 올바른
  server/tool dispatch를 검증한다.

이 변경은 공개 API 계약 확장이므로 기존 배포 endpoint를 삭제하지 말고 새
PlayMCP in KC endpoint에서 `list_tools == 92`, 내부 인벤토리 `16/82`, 대표
실제 OpenDART 호출을 통과한 뒤 본선 endpoint를 교체한다. 구체적인 배포 절차는
[카카오 PlayMCP 운영·갱신 핸드북](KAKAO_PLAYMCP_OPERATIONS_KO.md)을 따른다.
