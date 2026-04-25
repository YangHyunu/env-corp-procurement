---
title: G2B OpenAPI 공통 가이드
provider: g2b
applies_to:
  - BidPublicInfoService  # 입찰공고
  - ScsbidInfoService      # 낙찰·개찰결과
status: living-doc
last_verified: 2026-04-25
---

# G2B OpenAPI 공통 가이드 (`_common.md`)

이 문서는 모든 G2B(나라장터) API 문서가 참조하는 **공통 규칙·정책·도메인 상수·유틸 코드** 모음이다. 개별 API 문서(`getBidPblancListInfoThngPPSSrch.md` 등)는 이 문서를 전제로 작성된다.

## 목차

1. [사용 가능 API 인덱스](#사용-가능-api-인덱스)
2. [Endpoint 패턴](#endpoint-패턴)
3. [인증 (ServiceKey)](#인증-servicekey)
4. [공통 요청 파라미터](#공통-요청-파라미터)
5. [공통 응답 구조](#공통-응답-구조)
6. [에러 처리](#에러-처리)
7. [재시도·타임아웃 정책](#재시도타임아웃-정책)
8. [페이징](#페이징)
9. [조회 기간 제약 (1개월 윈도우)](#조회-기간-제약-1개월-윈도우)
10. [시간 포맷 처리](#시간-포맷-처리)
11. [입찰공고번호 체계](#입찰공고번호-체계)
12. [BRN(사업자등록번호) 정규화](#brn사업자등록번호-정규화)
13. [참가제한지역코드 표](#참가제한지역코드-표)
14. [도메인 상수 — 한국환경공단](#도메인-상수--한국환경공단)
15. [Python 공통 모듈](#python-공통-모듈)
16. [저장 레이어 (메달리온)](#저장-레이어-메달리온)
17. [Airflow DAG 패턴](#airflow-dag-패턴)
18. [갱신 주기 & 수집 정책](#갱신-주기--수집-정책)
19. [알려진 함정 체크리스트](#알려진-함정-체크리스트)

---

## 사용 가능 API 인덱스

현재 분석 파이프라인에 포함된 G2B API 4종.

| 번호 | operationId | 역할 | 문서 |
|---|---|---|---|
| 14 | `getBidPblancListInfoThngPPSSrch` | seed (입찰공고 풀 생성) | `getBidPblancListInfoThngPPSSrch.md` |
| 5 | `getOpengResultListInfoThng` | 개찰결과 (유찰/협상 식별) | `getOpengResultListInfoThng.md` |
| 1 | `getScsbidListSttusThng` | **BRN 추출 ⭐** (최종 낙찰자) | `getScsbidListSttusThng.md` |
| 9 | `getOpengResultListInfoThngPreparPcDetail` | 복수예가 디테일 (옵션) | `getOpengResultListInfoThngPreparPcDetail.md` |

호출 흐름:

```
14번 (공고 풀)
   │ bidNtceNo
   ├─► 5번 (개찰결과 — 유찰 포함)
   │     │
   │     │ progrsDivCdNm == '개찰완료'
   │     ▼
   │   1번 (최종 낙찰자 BRN)
   │     │
   │     │ bidwinnrBizno
   │     ▼
   │   SR 인증 / 부정당제재 / ...  (외부 API)
   │
   └─► 9번 (복수예가, rsrvtnPrceFileExistnceYn=Y인 경우)
```

⚠️ `getScsbidListSttusThngPPSSrch` (16번)는 1번의 **검색조건 확장 변형**으로 별개 API. 일반적으로 1번 우선 사용.

---

## Endpoint 패턴

```
http://apis.data.go.kr/1230000/{path}/{Service}/{operationId}
```

| 서비스 | path | 소속 API |
|---|---|---|
| `BidPublicInfoService` | `/ad/` | 14번 (입찰공고) |
| `ScsbidInfoService` | `/as/` | 1·5·9번 (낙찰·개찰결과) |

> **HTTPS 미지원**. `http://`로만 호출. 서비스가 https로 응답하지 않는 케이스 다수 — 운영망에서 outbound `http` 허용 필요.

---

## 인증 (ServiceKey)

- 공공데이터포털 발급 키. 활용신청 후 **승인 상태** 확인 필수.
- 키는 **Encoding 키**와 **Decoding 키** 두 종류로 제공됨:
  - `requests.get(url, params={"ServiceKey": key, ...})` — **Decoding 키** 사용 (라이브러리가 알아서 인코딩)
  - URL에 직접 박을 때 — **Encoding 키** 사용 (이미 인코딩된 형태)
- 둘이 섞이면 `SERVICEKEY_TYPE_ERROR` (HTTP 200 + 게이트웨이 에러).

### 환경변수 표준

```bash
export G2B_SERVICE_KEY="발급받은_Decoding_키"
```

코드에 하드코딩 금지. 모든 스크립트·DAG는 `os.environ["G2B_SERVICE_KEY"]`로만 접근.

---

## 공통 요청 파라미터

모든 API가 공유하는 파라미터.

| name | required | size | 설명 |
|---|---|---|---|
| `ServiceKey` | ✅ | 400 | Decoding 키 |
| `numOfRows` | ✅ | 4 | 페이지 크기 (실측 최대 999 추정) |
| `pageNo` | ✅ | 4 | 1부터 시작 |
| `type` | ❌ | 4 | `xml`(기본) / `json` |
| `inqryDiv` | ✅ | 1 | API마다 의미 다름 (각 문서 참조) |
| `inqryBgnDt` | 조건부 | 12 | `YYYYMMDDHHMM` |
| `inqryEndDt` | 조건부 | 12 | `YYYYMMDDHHMM` |
| `bidNtceNo` | 조건부 | 11~40 | `inqryDiv`가 입찰공고번호 모드일 때 필수 |

### `inqryDiv` 의미가 API마다 다름 ⚠️

같은 이름·다른 의미. 절대 혼동 주의:

| `inqryDiv` | 14번 | 1번 | 5번 | 9번 |
|---|---|---|---|---|
| `1` | 공고게시일시 | 등록일시 | 입력일시 | 입력일시 |
| `2` | 개찰일시 | 공고일시 | 공고일시 | **입찰공고번호** |
| `3` | — | 개찰일시 | 개찰일시 | — |
| `4` | — | **입찰공고번호** | **입찰공고번호** | — |

---

## 공통 응답 구조

### 정상 응답 (XML 기본)

```xml
<response>
  <header>
    <resultCode>00</resultCode>
    <resultMsg>정상</resultMsg>
  </header>
  <body>
    <items>
      <item> ... </item>
      <item> ... </item>
    </items>
    <numOfRows>10</numOfRows>
    <pageNo>1</pageNo>
    <totalCount>584</totalCount>
  </body>
</response>
```

### 정상 응답 (JSON, `type=json` 시)

```json
{
  "response": {
    "header": {"resultCode": "00", "resultMsg": "정상"},
    "body": {
      "items": [{...}, {...}],
      "numOfRows": 10,
      "pageNo": 1,
      "totalCount": 584
    }
  }
}
```

> XML 응답은 `<items><item/></items>` 구조이지만 JSON에서는 `items`가 그냥 배열로 평탄화될 수 있음. 파서 분기 주의.

### 빈 결과 정상 응답

```xml
<response>
  <header><resultCode>00</resultCode><resultMsg>정상</resultMsg></header>
  <body>
    <items/>
    <numOfRows>10</numOfRows><pageNo>1</pageNo><totalCount>0</totalCount>
  </body>
</response>
```

`<items/>` 빈 태그 + `totalCount=0` — **에러 아님**, 단지 조건 매칭 0건.

---

## 에러 처리

### 1) `resultCode != "00"` (응답 본문 에러)

| resultCode | 의미 | 대응 |
|---|---|---|
| `00` | 정상 | — |
| `99` | 기타 오류 | 재시도 + 로깅 |
| (그 외) | 미문서화 코드 | 로깅 후 운영자 확인 |

### 2) 게이트웨이 에러 (`OpenAPI_ServiceResponse`)

ServiceKey·활용신청·트래픽 한도 등은 응답 루트가 다르게 옴:

```xml
<OpenAPI_ServiceResponse>
  <cmmMsgHeader>
    <errMsg>SERVICE ERROR</errMsg>
    <returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg>
    <returnReasonCode>30</returnReasonCode>
  </cmmMsgHeader>
</OpenAPI_ServiceResponse>
```

자주 나오는 `returnAuthMsg`:

| 메시지 | 의미 | 대응 |
|---|---|---|
| `SERVICE_KEY_IS_NOT_REGISTERED_ERROR` | 키 미등록 | 공공데이터포털에서 활용신청·승인 확인 |
| `LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR` | 일일 한도 초과 | 다음날까지 대기 또는 한도 증액 신청 |
| `SERVICEKEY_TYPE_ERROR` | Encoding/Decoding 키 혼동 | Decoding 키 사용 + `params=` 통해 전달 |
| `INVALID_REQUEST_PARAMETER_ERROR` | 파라미터 오류 (날짜 범위 초과 등) | 1개월 윈도우로 분할 |
| `UNREGISTERED_IP_ERROR` | IP 등록 필요 | IP 화이트리스트 추가 |

### 3) HTTP 에러

| 코드 | 의미 |
|---|---|
| `200` | 응답 본문 내부 결과코드로 분기 (위 1·2번) |
| `403` | 보통 ServiceKey 또는 IP 문제 |
| `5xx` | 서버 측 일시 장애 → 재시도 |

### 응답 분기 우선순위

```
1) HTTP status != 200 → 즉시 실패
2) root tag == "OpenAPI_ServiceResponse" → 게이트웨이 에러
3) header.resultCode != "00"             → 응답 에러
4) totalCount == 0                       → 정상, 0건
5) 그 외                                  → 정상 데이터
```

---

## 재시도·타임아웃 정책

표준 정책:

| 항목 | 값 |
|---|---|
| 연결 타임아웃 | 10초 |
| 읽기 타임아웃 | **60초** (서버 응답 느림. 15초로는 자주 timeout) |
| 재시도 횟수 | 5회 |
| 백오프 | 지수 (1, 2, 4, 8, 16초) + jitter |
| 재시도 대상 | `ReadTimeout`, `ConnectionError`, HTTP 5xx |
| **재시도 안 함** | 4xx, 게이트웨이 에러 (`SERVICE_KEY_*`) |

게이트웨이 에러는 **재시도해도 결과가 같다** — 즉시 실패시키고 알림.

---

## 페이징

### 패턴

```
1) page=1 호출 → totalCount 확인
2) total_pages = ceil(totalCount / numOfRows)
3) page=2..total_pages 호출
4) 각 호출 사이 sleep 0.1s (rate limit 보호)
```

### `numOfRows` 권장값

- 입찰공고(14번) — 100~999
- 낙찰·개찰결과 — 100 (대부분 한 공고당 1~수 건)
- 복수예가(9번) — 15~30 (한 공고당 보통 15건)

### 중복·누락 위험

같은 검색조건으로 페이징하는 사이 새 데이터가 끼어들면 중복/누락 발생 가능 → **`bidNtceNo` 또는 `(bidNtceNo, bidNtceOrd)` 기준 dedupe** 필수.

---

## 조회 기간 제약 (1개월 윈도우)

`inqryBgnDt` ~ `inqryEndDt` 범위가 **약 30일**을 넘으면 게이트웨이가 `INVALID_REQUEST_PARAMETER_ERROR` 또는 "입력범위값 초과" 응답. **실측 검증됨** (2026-04-25, 14번 API).

### 백필 전략

```python
# 한 달씩 슬라이딩
def month_windows(start: date, end: date, days: int = 30):
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=days), end)
        yield (
            cur.strftime("%Y%m%d") + "0000",
            nxt.strftime("%Y%m%d") + "2359",
        )
        cur = nxt + timedelta(days=1)
```

Airflow에서는 **Dynamic Task Mapping(`expand`)**으로 월 윈도우 리스트를 매핑해서 병렬 처리.

---

## 시간 포맷 처리

### 요청 (12자리)

```
YYYYMMDDHHMM      예: 202604010000
```

### 응답 (3가지 혼재)

| 포맷 | 자릿수 | 예시 | 출현 필드 |
|---|---|---|---|
| `YYYY-MM-DD HH:MM:SS` | 19 | `2025-07-01 11:07:08` | 대부분의 일시 필드 |
| `YYYY-MM-DD HH:MM` | 16 | `2026-04-02 18:00` | `bidQlfctRgstDt`, `cmmnSpldmdAgrmntClseDt`, `dlvrTmlmtDt` 등 일부 |
| `YYYY-MM-DD` | 10 | `2025-07-23` | `fnlSucsfDate` |

파서는 **세 포맷 모두 허용** 필요:

```python
from datetime import datetime, date

def parse_dt(s: str):
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unknown date format: {s!r}")
```

### 시간대

응답 시각은 **모두 KST(UTC+9)**로 가정. tzinfo 없이 들어오므로 저장 시 명시적으로 부여:

```python
from zoneinfo import ZoneInfo
KST = ZoneInfo("Asia/Seoul")
dt_naive = parse_dt(s)
dt_kst = dt_naive.replace(tzinfo=KST) if dt_naive else None
```

PostgreSQL 저장은 `TIMESTAMP WITH TIME ZONE`(`timestamptz`) 권장.

---

## 입찰공고번호 체계

차세대 나라장터 표준: **13자리** (`R + 년도2 + 단계구분2 + 순번8`).

| 단계구분 | 의미 |
|---|---|
| `BK` | 입찰 |
| `TA` | 계약 |
| `DD` | 발주계획 |
| `BD` | 사전규격 |
| `BM` | 통합공고 |

예: `R25BK00845027` = 2025년 입찰 845027번

### ⚠️ size 정의 vs 실제 불일치

명세서의 size 값은 일관되지 않음:

| 필드 | 명세 size | 실제 |
|---|---|---|
| `bidNtceNo` (14번 응답) | 40 | 13 |
| `bidNtceNo` (1번 응답) | 40 | 13 |
| `bidNtceNo` (5번 응답) | 11 | 13 |
| `bidNtceNo` (9번 응답) | 11 | 13 |
| `bidNtceNo` (5번 요청 파라미터) | 11 | 13으로 보내도 동작 |

**규칙: size 정의 무시하고 항상 13자리로 처리**. DB 컬럼은 `VARCHAR(20)` 정도 여유 있게.

---

## BRN(사업자등록번호) 정규화

분석의 **통합 조인 키**. 모든 데이터셋이 BRN으로 합쳐진다.

### 표준 형태

**하이픈 없는 10자리 숫자 문자열** (`"1408121883"`).

### 정규화 함수

```python
import re

def normalize_brn(s: str) -> str | None:
    """
    "123-45-67890", "1234567890", " 123 - 45 - 67890 " 등을
    모두 "1234567890"으로 변환.
    유효하지 않으면 None.
    """
    if not s:
        return None
    digits = re.sub(r"\D", "", s)
    if len(digits) != 10:
        return None
    return digits
```

### 데이터 소스별 BRN 출처

| 소스 | 필드 | 형태 |
|---|---|---|
| 1번 API | `bidwinnrBizno` | 이미 10자리 (정규화 거의 불필요) |
| 5번 API `opengCorpInfo` | caret 두 번째 토큰 | 이미 10자리 |
| (외부 SR API들) | 각자 다름 | 하이픈 포함 가능 → 정규화 필요 |

---

## 참가제한지역코드 표

`prtcptLmtRgnCd` (요청), `rgnLmtBidLocplcJdgmBssCd` 등에서 사용.

| 코드 | 지역 | 코드 | 지역 |
|---|---|---|---|
| `00` | **전국** (지역제한 없음) | `41` | 경기도 |
| `11` | 서울특별시 | `42` | 강원도 |
| `26` | 부산광역시 | `43` | 충청북도 |
| `27` | 대구광역시 | `44` | 충청남도 |
| `28` | 인천광역시 | `45` | 전라북도 |
| `29` | 광주광역시 | `46` | 전라남도 |
| `30` | 대전광역시 | `47` | 경상북도 |
| `31` | 울산광역시 | `48` | 경상남도 |
| `36` | 세종특별자치시 | `50` | 제주도 |
| `51` | 강원특별자치도 | `52` | 전북특별자치도 |
| `99` | 기타 | | |

업체 주소 → 광역시도 매핑은 별도 사전 필요 (`충청남도 아산시` → `44`).

---

## 도메인 상수 — 한국환경공단

**실측 검증 (2026-04-25, 최근 1년 발주 기준)**:

```python
# 한국환경공단 본사 + 산하 8개 권역본부 + 사업단 = 총 10개 dminsttCd
ENV_CORP_DMINSTT_CDS = [
    "B552584",  # 한국환경공단 (본사)                        — 134건/년
    "Z008653",  # 한국환경공단 수도권서부환경본부              —  77건/년
    "Z004865",  # 한국환경공단 수도권동부환경본부              —  68건/년
    "Z018993",  # 한국환경공단 충청권환경본부                  —  64건/년
    "Z004863",  # 한국환경공단 부산울산경남환경본부            —  42건/년
    "Z003477",  # 한국환경공단 대구경북환경본부                —  40건/년
    "Z004864",  # 한국환경공단 광주전남제주환경본부            —  31건/년
    "Z042470",  # 한국환경공단 강원환경본부                    —   8건/년
    "D266078",  # 한국환경공단 국가물산업클러스터사업단        —   6건/년
    "Z042433",  # 한국환경공단 전북환경본부                    —   2건/년
]

ENV_CORP_DMINSTT_NAMES = {
    "B552584": "한국환경공단",
    "Z008653": "한국환경공단 수도권서부환경본부",
    "Z004865": "한국환경공단 수도권동부환경본부",
    "Z018993": "한국환경공단 충청권환경본부",
    "Z004863": "한국환경공단 부산울산경남환경본부",
    "Z003477": "한국환경공단 대구경북환경본부",
    "Z004864": "한국환경공단 광주전남제주환경본부",
    "Z042470": "한국환경공단 강원환경본부",
    "D266078": "한국환경공단 국가물산업클러스터사업단",
    "Z042433": "한국환경공단 전북환경본부",
}
```

> 코드 prefix(`B`/`D`/`Z`)에는 의미 있는 패턴 없음. 하드코딩 매핑이 정답.
> 신규 본부 신설 시 매핑 갱신 필요 — 분기당 1회 검증 DAG 권장.

---

## Python 공통 모듈

`g2b_common.py` 단일 파일로 작성. 모든 수집 DAG가 이 모듈만 import.

```python
"""g2b_common.py — G2B OpenAPI 공통 유틸."""
from __future__ import annotations

import os
import re
import time
import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from typing import Iterator
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")

# ── 환경 ─────────────────────────────────────────────────
SERVICE_KEY = os.environ["G2B_SERVICE_KEY"]
BASE_URL = "http://apis.data.go.kr/1230000"

# ── 도메인 상수 ──────────────────────────────────────────
ENV_CORP_DMINSTT_CDS = [
    "B552584", "Z008653", "Z004865", "Z018993", "Z004863",
    "Z003477", "Z004864", "Z042470", "D266078", "Z042433",
]


# ── HTTP 세션 (재시도 내장) ─────────────────────────────
def make_session(
    total_retries: int = 5,
    backoff_factor: float = 1.0,
) -> requests.Session:
    """재시도·백오프가 적용된 requests.Session."""
    session = requests.Session()
    retry = Retry(
        total=total_retries,
        backoff_factor=backoff_factor,  # 1, 2, 4, 8, 16
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# ── 호출 ───────────────────────────────────────────────
class G2BApiError(Exception):
    """게이트웨이 에러 또는 resultCode != '00'."""


def call(
    operation_path: str,        # 예: "ad/BidPublicInfoService/getBidPblancListInfoThngPPSSrch"
    params: dict,
    session: requests.Session | None = None,
    timeout: tuple[int, int] = (10, 60),
) -> ET.Element:
    """
    G2B API 호출 → 정상이면 <body> Element 반환.
    게이트웨이/응답 에러는 G2BApiError 발생.
    """
    session = session or make_session()
    url = f"{BASE_URL}/{operation_path}"
    full_params = {"ServiceKey": SERVICE_KEY, **params}

    r = session.get(url, params=full_params, timeout=timeout)
    r.raise_for_status()

    root = ET.fromstring(r.text)

    # 게이트웨이 에러
    if root.tag == "OpenAPI_ServiceResponse":
        auth = root.findtext(".//returnAuthMsg") or "(none)"
        reason = root.findtext(".//returnReasonCode") or "(none)"
        raise G2BApiError(f"Gateway error: {auth} (code={reason})")

    # 정상 응답 에러
    code = root.findtext(".//resultCode")
    if code != "00":
        msg = root.findtext(".//resultMsg")
        raise G2BApiError(f"resultCode={code}, msg={msg}")

    return root


# ── 페이징 ─────────────────────────────────────────────
def paginate(
    operation_path: str,
    params: dict,
    page_size: int = 100,
    session: requests.Session | None = None,
    sleep_sec: float = 0.1,
) -> Iterator[ET.Element]:
    """페이징 끝까지 돌면서 <item> Element를 yield."""
    session = session or make_session()
    page = 1
    while True:
        p = {**params, "pageNo": str(page), "numOfRows": str(page_size), "type": "xml"}
        root = call(operation_path, p, session=session)

        items = root.findall(".//item")
        for it in items:
            yield it

        total = int(root.findtext(".//totalCount") or "0")
        if not items or page * page_size >= total:
            break
        page += 1
        time.sleep(sleep_sec)


# ── 윈도우 분할 ────────────────────────────────────────
def month_windows(start: date, end: date, days: int = 30) -> Iterator[tuple[str, str]]:
    """1개월 윈도우 제약 회피용 (bgn, end) 문자열 쌍 yield."""
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=days), end)
        yield (
            cur.strftime("%Y%m%d") + "0000",
            nxt.strftime("%Y%m%d") + "2359",
        )
        cur = nxt + timedelta(days=1)


# ── 정규화 ─────────────────────────────────────────────
def normalize_brn(s: str | None) -> str | None:
    """사업자등록번호 → 10자리 숫자 문자열. 유효하지 않으면 None."""
    if not s:
        return None
    digits = re.sub(r"\D", "", s)
    return digits if len(digits) == 10 else None


def normalize_corp_name(s: str | None) -> str | None:
    """업체명 정규화: (주)/주식회사/(유)/유한회사 통일, 공백 정리."""
    if not s:
        return None
    s = s.strip()
    s = re.sub(r"\(주\)|주식회사", "", s)
    s = re.sub(r"\(유\)|유한회사", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def parse_dt(s: str | None) -> datetime | None:
    """G2B 응답의 3가지 시간 포맷 모두 파싱 (KST tzinfo 부여)."""
    if not s or not s.strip():
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=KST)
        except ValueError:
            continue
    logger.warning("Unknown date format: %r", s)
    return None


def to_int(s: str | None) -> int | None:
    """숫자 문자열 → int. 빈 문자열·비숫자는 None."""
    if not s or not s.strip():
        return None
    try:
        return int(s.strip())
    except ValueError:
        return None


def to_float(s: str | None) -> float | None:
    """숫자 문자열 → float."""
    if not s or not s.strip():
        return None
    try:
        return float(s.strip())
    except ValueError:
        return None


# ── 파서 헬퍼 ──────────────────────────────────────────
def parse_openg_corp_info(s: str | None) -> dict:
    """
    5번 API의 opengCorpInfo caret 분리 파싱.
    case ∈ {"single", "multiple", "negotiation", "empty", "malformed"}
    """
    if not s or not s.strip():
        return {"case": "empty", "winner_name": None, "brn": None,
                "ceo_name": None, "bid_amount": None, "bid_rate": None}

    tokens = s.split("^")

    if tokens[0].startswith("낙찰예정자 다수"):
        return {
            "case": "multiple",
            "winner_name": None,
            "brn": None,
            "ceo_name": None,
            "bid_amount": to_int(tokens[-2]) if len(tokens) >= 2 else None,
            "bid_rate":   to_float(tokens[-1]) if len(tokens) >= 1 else None,
        }

    if len(tokens) >= 5:
        has_amount = bool(tokens[3].strip()) and bool(tokens[4].strip())
        return {
            "case": "single" if has_amount else "negotiation",
            "winner_name": tokens[0] or None,
            "brn":         normalize_brn(tokens[1]),
            "ceo_name":    tokens[2] or None,
            "bid_amount":  to_int(tokens[3]),
            "bid_rate":    to_float(tokens[4]),
        }

    return {"case": "malformed", "raw": s, "winner_name": None, "brn": None,
            "ceo_name": None, "bid_amount": None, "bid_rate": None}
```

---

## 저장 레이어 (메달리온)

PostgreSQL을 마스터로 두고, 분석 가속 캐시는 Parquet/DuckDB 옵션.

| 계층 | prefix | 저장소 | 내용 |
|---|---|---|---|
| Bronze | `raw_*` | Parquet (`yyyy=/mm=/dd=` 파티션) + PostgreSQL | API 응답 원본 + 수집시각 |
| Silver | `stg_*` | PostgreSQL | 정규화·dedupe·유효성 플래그 |
| Gold | `mart_*` | PostgreSQL | 분석 와이드 테이블 |

### 표준 raw 테이블 컬럼

```sql
CREATE TABLE raw_<source> (
    fetched_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    operation_id      TEXT NOT NULL,
    request_params    JSONB NOT NULL,
    item_xml          TEXT NOT NULL,        -- 또는 item_json JSONB
    bid_ntce_no       VARCHAR(20),          -- 추출 가능한 경우
    bid_ntce_ord      VARCHAR(5),
    PRIMARY KEY (operation_id, fetched_at, bid_ntce_no, bid_ntce_ord)
);
```

### 주요 stg/mart 테이블

- `stg_bid_notice` — 14번 정규화
- `stg_award` — 1번 정규화 (BRN 추출)
- `stg_opening_result` — 5번 정규화 (`opengCorpInfo` 파싱)
- `stg_prepar_price` — 9번 정규화
- `mart_company_sr` — BRN 단위, SR 인증 멀티-핫
- `mart_item_supply` — (세부품명번호, BRN) 단위
- `mart_item_density` — 세부품명번호 단위 공급망 밀도

---

## Airflow DAG 패턴

### DAG 분리 원칙

- **수집(ingest) DAG는 API별로 분리** — 갱신 주기·1개월 윈도우 등 정책이 다름
- **mart/feature/model DAG는 Dataset 트리거**로 ingest 갱신을 받아 자동 실행

### 표준 ingest 태스크 패턴

```
fetch_api → validate_schema → write_raw_parquet → upsert_postgres_raw → emit_dataset
```

### 백필 (1개월 윈도우 + Dynamic Task Mapping)

```python
@task
def make_windows(start: str, end: str) -> list[dict]:
    return [
        {"inqryBgnDt": b, "inqryEndDt": e}
        for b, e in month_windows(date.fromisoformat(start), date.fromisoformat(end))
    ]

@task
def fetch_window(window: dict) -> int:
    items = list(paginate(
        "ad/BidPublicInfoService/getBidPblancListInfoThngPPSSrch",
        params={"inqryDiv": "1", **window},
        page_size=100,
    ))
    # ... raw 저장 ...
    return len(items)

with DAG("backfill_g2b_bid", ...) as dag:
    windows = make_windows("2024-01-01", "2026-04-25")
    fetch_window.expand(window=windows)  # 윈도우당 병렬
```

### 환경공단 필터 호출 패턴 (10개 코드 순회)

```python
@task
def fetch_one_org(dminstt_cd: str, window: dict):
    items = list(paginate(
        "ad/BidPublicInfoService/getBidPblancListInfoThngPPSSrch",
        params={
            "inqryDiv": "1",
            "dminsttCd": dminstt_cd,
            **window,
        },
    ))
    # ... 저장 ...

# 10개 본부 × N개 윈도우 → expand로 병렬화
fetch_one_org.expand_kwargs([
    {"dminstt_cd": cd, "window": w}
    for cd in ENV_CORP_DMINSTT_CDS
    for w in windows
])
```

---

## 갱신 주기 & 수집 정책

| 데이터셋 | 원천 갱신 | 수집 빈도 | DAG 스케줄 |
|---|---|---|---|
| 14번 입찰공고 | 분~시간 | 일 1회 | `0 6 * * *` |
| 5번 개찰결과 | 당일 | 일 1회 | `0 7 * * *` |
| 1번 낙찰자 | 개찰 후 1~2일 | 일 1회 | `0 8 * * *` |
| 9번 복수예가 | 당일 | 일 1회 (5번에서 `Y`인 공고만) | `0 9 * * *` |
| 환경공단 코드 검증 | 분기 | 분기 1회 | `0 0 1 */3 *` |

### 캐싱 가이드

- 같은 `bidNtceNo` 조회는 **로컬 라이프타임 5분** 캐시 (raw 단계)
- mart 갱신은 ingest의 Dataset 트리거로
- BRN별 SR 인증 정보는 24h 캐시 (외부 API)

---

## 알려진 함정 체크리스트

수집·정제 코드 리뷰 시 이 리스트로 확인:

- [ ] `bidNtceNo`는 size 정의 무시하고 13자리 그대로 저장
- [ ] `bidNtceOrd`는 항상 3자리 zero-pad (`"000"`, `"001"`, ...)
- [ ] 모든 일시 필드는 3가지 포맷 (`19/16/10`자리) 모두 허용 파서 사용
- [ ] 모든 시각은 KST tzinfo 부여 후 저장
- [ ] BRN은 하이픈 제거 후 10자리 정규화, 그 외 길이는 `null`
- [ ] 업체명은 `(주)`/`주식회사` 등 통일 후 매칭
- [ ] 빈 문자열 `""`은 모두 `null`로 정규화
- [ ] `inqryDiv`는 API마다 의미 다름 — 각 문서 표 참조 후 사용
- [ ] 1개월 넘는 기간은 자동 분할 (`month_windows`)
- [ ] 핸드폰번호 마스킹 `*`은 `null`로 정규화 (`bidwinnrTelNo`)
- [ ] `opengCorpInfo`는 단순 split 금지, `parse_openg_corp_info` 사용
- [ ] `purchsObjPrdctList`는 다건 가능 — explode 후 분석
- [ ] 페이징 시 `(bidNtceNo, bidNtceOrd)` 기준 dedupe
- [ ] 게이트웨이 에러는 재시도 안 함 (즉시 알림)
- [ ] HTTP 5xx만 재시도 (4xx는 즉시 실패)
- [ ] `prtcptCnum=0` + `progrsDivCdNm=유찰` 조합으로 진짜 유찰 식별
- [ ] 응답 XML이 단일 `<item>`인 경우 일부 파서가 배열 아닌 객체로 반환 — 항상 배열 정규화
- [ ] ServiceKey는 환경변수에서만 읽기, 코드/git/로그에 노출 금지

---

## 미해결 / 향후 검증 필요

- [ ] `numOfRows` 정확한 최대값 (실측 999 동작 확인됨, 9999 가능 여부 미확인)
- [ ] 일일 호출 한도 정확한 수치 (활용신청 등급별)
- [ ] 9번 API의 응답 schema가 명세대로인지 (실측 미수행)
- [ ] `opengCorpInfo`의 다수 낙찰자/협상 케이스 토큰 구조 실측 검증
- [ ] HTTPS 지원 여부 재확인 (현재는 HTTP만 가정)
- [ ] JSON 응답 시 `items` 직렬화 형태 (배열 vs 객체) — 단일 결과 케이스
