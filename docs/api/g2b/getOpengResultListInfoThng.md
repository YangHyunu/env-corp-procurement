---
operationId: getOpengResultListInfoThng
operationNo: 5
provider: g2b
service: ScsbidInfoService
type: query-list
role: opening-result
aliases:
  - 개찰결과
  - 개찰완료
  - 유찰
  - 재입찰
  - 1순위 투찰
  - 투찰결과
  - 개찰업체
related:
  - getScsbidListSttusThng           # 1번 — 최종낙찰자 (확정된 결과)
  - getOpengResultListInfoThngPreparPcDetail  # 9번 — 같은 공고의 복수예가 디테일
status: documented
---

# 개찰결과 물품 목록 조회

`getOpengResultListInfoThng`

물품 입찰의 **개찰결과**(유찰/개찰완료/재입찰)를 조회한다. 1번 API(`getScsbidListSttusThng`)가 **최종 낙찰자만** 반환하는 것과 달리, 본 API는 **유찰 건과 1순위 투찰자**까지 포함한다. 공급망 분석에서 **유찰 패턴(공급사 부족 시그널)**을 잡는 데 필수.

## 메타

| 항목 | 값 |
|---|---|
| operationId | `getOpengResultListInfoThng` |
| operationNo | 5 |
| 유형 | 조회(목록) |
| 서비스 | ScsbidInfoService (낙찰정보) |
| 제공 | 조달청 / NIA 한국정보화진흥원 |
| Callback URL | N/A |
| 최대 메시지 사이즈 | 4000 bytes |
| 평균 응답 시간 | 500 ms |
| 초당 최대 트랜잭션 | 30 TPS |

## ⚠️ 1번 API와의 차이 (꼭 짚을 것)

| 구분 | **본 API (5번)** | 1번 (`getScsbidListSttusThng`) |
|---|---|---|
| 데이터 단위 | 개찰 시점의 **1순위 투찰자** | **최종 낙찰자** (협상 등 거친 후) |
| 유찰 포함? | ✅ 포함 (`progrsDivCdNm=유찰`) | ❌ 제외 (낙찰자가 있어야 row 생성) |
| 재입찰 포함? | ✅ 포함 (`progrsDivCdNm=재입찰`) | (재입찰 차수의 낙찰자만) |
| 협상에 의한 계약? | 투찰금액·투찰율 **미공개** | 최종낙찰금액 공개 |
| 업체 정보 형태 | `opengCorpInfo` **단일 필드에 caret 묶음** | 4개 필드(`bidwinnrNm`/`Bizno`/`CeoNm`/`Adrs`)로 분리 |
| 분석 활용 | 공급망 밀도·유찰률·경쟁 패턴 | 최종 낙찰자 BRN 추출 |

**둘 다 같이 써야 그림이 완성된다** — 5번으로 "어떤 공고가 유찰됐나" 분석하고, 1번으로 "낙찰된 공고의 최종 낙찰자가 누구인가" 확정.

## Endpoint

```
GET http://apis.data.go.kr/1230000/as/ScsbidInfoService/getOpengResultListInfoThng
```

## Request Parameters

| name | ko | required | size | sample | note |
|---|---|---|---|---|---|
| `ServiceKey` | 서비스키 | ✅ | 400 | (인증키) | 공공데이터포털 발급. URL 인코딩 필수 |
| `numOfRows` | 한 페이지 결과 수 | ✅ | 4 | 10 | |
| `pageNo` | 페이지 번호 | ✅ | 4 | 1 | |
| `inqryDiv` | 조회구분 | ✅ | 1 | 1 | `1`=입력일시 / `2`=공고일시 / `3`=개찰일시 / `4`=입찰공고번호 |
| `type` | 응답 타입 | ❌ | 4 | `json` | 생략 시 XML, `json` 명시 시 JSON |
| `inqryBgnDt` | 조회시작일시 | 조건부 | 12 | `202507010000` | `YYYYMMDDHHMM`. `inqryDiv=1·2·3`일 때 필수 |
| `inqryEndDt` | 조회종료일시 | 조건부 | 12 | `202507012359` | 동상 |
| `bidNtceNo` | 입찰공고번호 | 조건부 | 11 | `R25BK00840922` | `inqryDiv=4`일 때 필수. 실제 데이터는 13자리 |

## 호출 규칙 (에이전트용)

### `inqryDiv` 분기 (1번 API와 동일)

| `inqryDiv` | 의미 | 필수 추가 파라미터 | 권장 용도 |
|---|---|---|---|
| `1` | 입력일시 (개찰결과 시스템 입력 시점) | `inqryBgnDt`, `inqryEndDt` | 일별 증분 수집 |
| `2` | 공고일시 | `inqryBgnDt`, `inqryEndDt` | 공고일 기준 분석 |
| `3` | 개찰일시 | `inqryBgnDt`, `inqryEndDt` | 개찰일 기준 분석 |
| `4` | 입찰공고번호 | `bidNtceNo` | **공고 풀 → 개찰결과 룩업** |

### 분석 파이프라인 표준 호출 패턴

```python
# 14번에서 모은 bidNtceNo 풀의 개찰결과 일괄 조회
for bid_ntce_no in bid_ntce_no_pool:
    rows = get_openg_result(
        inqryDiv=4,
        bidNtceNo=bid_ntce_no,
        numOfRows=10,
        pageNo=1,
    )
    # rows[*].progrsDivCdNm로 분기:
    #   '유찰'   → 공급망 빈약 시그널, 후속 1번 API 호출 불필요
    #   '개찰완료' → 후속 1번 API로 최종 낙찰자 확정
    #   '재입찰' → 다음 차수의 결과를 다시 조회
```

또는 일별 증분 수집:

```python
# 어제 입력된 모든 개찰결과
get_openg_result(
    inqryDiv=1,
    inqryBgnDt=f"{yesterday}0000",
    inqryEndDt=f"{yesterday}2359",
    numOfRows=999,
    pageNo=1,
)
```

## Response Parameters

응답은 `<response><header/><body><items><item/>...</items></body></response>` 구조.

### Header

| name | ko | size | required | note |
|---|---|---|---|---|
| `resultCode` | 결과코드 | 2 | ✅ | 정상 시 `00` |
| `resultMsg` | 결과메시지 | 50 | ✅ | 정상 시 `정상` |

### Body 페이지 메타

| name | ko | size | sample | note |
|---|---|---|---|---|
| `numOfRows` | 한 페이지 결과 수 | 4 | 10 | 요청값 echo |
| `pageNo` | 페이지 번호 | 4 | 1 | 요청값 echo |
| `totalCount` | 데이터 총 개수 | 4 | 17 | 페이징 분기에 사용 |

### item — 공고 식별자

| name | ko | size | required | sample | note |
|---|---|---|---|---|---|
| `bidNtceNo` | 입찰공고번호 | 11 | ✅ | `R25BK00840922` | 차세대 13자리. **size 정의(11) vs 실제(13) 불일치** — 1·9·14번과 동일한 함정 |
| `bidNtceOrd` | 입찰공고차수 | 3 | ✅ | `000` | 재공고/재입찰 발생 시 증가 |
| `bidClsfcNo` | 입찰분류번호 | 5 | ✅ | `1` | 동일 공고번호 내 집행일련번호 |
| `rbidNo` | 재입찰번호 | 3 | ✅ | `000` | |
| `bidNtceNm` | 입찰공고명 | 1000 | ✅ | `근접전자기장 내성 시험 시스템 구축` | |

### item — 개찰 정보 ⭐

이 섹션이 **이 API의 핵심**.

| name | ko | size | required | sample | note |
|---|---|---|---|---|---|
| `opengDt` | 개찰일시 | 19 | ✅ | `2025-06-17 11:00:00` | `YYYY-MM-DD HH:MM:SS` |
| `prtcptCnum` | 참가업체수 | 6 | ❌ | `2` | 0이면 유찰. 경쟁률 분석에 핵심 |
| `opengCorpInfo` | 개찰업체정보 | 500 | ✅ | `이엠테스트코리아 주식회사^1428139282^김종인^178750000^97.992` | **caret 구분 묶음 필드 — 파싱 규칙은 아래 별도 섹션 참조** |
| `progrsDivCdNm` | 진행구분코드명 | 4 | ✅ | `개찰완료` | `유찰` / `개찰완료` / `재입찰` 3가지 |
| `inptDt` | 입력일시 | 19 | ❌ | `2025-07-14 09:57:49` | `YYYY-MM-DD HH:MM:SS`. `inqryDiv=1`의 검색 기준 |
| `rsrvtnPrceFileExistnceYn` | 예비가격파일존재여부 | 1 | ❌ | `Y` | Y/N. Y면 9번 API로 복수예가 디테일 조회 가능 |
| `opengRsltNtcCntnts` | 개찰결과공지내용 | 4000 | ❌ | (긴 텍스트 또는 빈 값) | 공지사항 자유 텍스트. 빈 값 빈번 |

### item — 기관 정보

| name | ko | size | required | sample | note |
|---|---|---|---|---|---|
| `ntceInsttCd` | 공고기관코드 | 7 | ❌ | `1230137` | 행자부코드 우선 |
| `ntceInsttNm` | 공고기관명 | 200 | ❌ | `조달청 대구지방조달청` | |
| `dminsttCd` | 수요기관코드 | 7 | ❌ | `Z021943` | **한국환경공단 필터 시 핵심** |
| `dminsttNm` | 수요기관명 | 200 | ❌ | `대구경북첨단의료산업진흥재단` | |

> **항목구분**: ✅ 필수(1), ❌ 옵션(0).

## 🔥 `opengCorpInfo` 파싱 — 이 API의 가장 큰 함정

`opengCorpInfo`는 caret(`^`)으로 구분된 **단일 문자열 필드**다. 케이스 3가지로 포맷이 달라진다 — 파서가 이 분기를 모르면 BRN 추출 실패하거나 잘못된 값 추출.

### 케이스 1: 단일 낙찰자 (가장 흔함)

5개 토큰: `업체명^사업자번호^대표자명^투찰금액^투찰율`

```
이엠테스트코리아 주식회사^1428139282^김종인^178750000^97.992
   ↓                ↓        ↓       ↓         ↓
 업체명           BRN(10)  대표자  투찰금액(원) 투찰율(%)
```

### 케이스 2: 다수 낙찰자

`낙찰예정자 다수`라는 고정 문자열이 첫 토큰에 오고, **개찰순위 1위의 투찰금액·투찰율**만 보여준다.

```
낙찰예정자 다수^...^투찰금액^투찰율
```

> 정확한 토큰 개수와 빈 토큰 처리 방식은 실제 응답으로 검증 필요. 첫 토큰이 `낙찰예정자 다수`로 시작하면 다수 케이스로 분기.

### 케이스 3: 협상에 의한 계약

투찰금액·투찰율이 **미공개** → 마지막 두 토큰이 빈 값 또는 누락.

```
업체명^사업자번호^대표자명^^
```

### 파싱 의사코드

```python
def parse_openg_corp_info(s: str) -> dict:
    if not s or s.strip() == "":
        return {"case": "empty"}

    tokens = s.split("^")

    # Case 2: 다수 낙찰자
    if tokens[0].startswith("낙찰예정자 다수"):
        return {
            "case": "multiple",
            "winner_name": None,
            "brn": None,
            "ceo_name": None,
            "bid_amount": _to_int(tokens[-2]) if len(tokens) >= 2 else None,
            "bid_rate": _to_float(tokens[-1]) if len(tokens) >= 1 else None,
        }

    # Case 1 & 3: 단일 또는 협상
    if len(tokens) >= 5:
        return {
            "case": "single" if tokens[3] and tokens[4] else "negotiation",
            "winner_name": tokens[0] or None,
            "brn": tokens[1] or None,           # 10자리 BRN
            "ceo_name": tokens[2] or None,
            "bid_amount": _to_int(tokens[3]) if tokens[3] else None,
            "bid_rate": _to_float(tokens[4]) if tokens[4] else None,
        }

    # 예외: 토큰 수 부족
    return {"case": "malformed", "raw": s}
```

### 함정 요약

- 업체명 자체에 `^`가 들어있을 가능성은 낮지만 0은 아님 → `split("^", maxsplit=4)` 권장
- 투찰금액은 정수, 투찰율은 소수(`97.992`) — 형변환 분기
- 다수 낙찰자 케이스는 BRN/업체명 모두 결측 → 1번 API로 후속 보강 필요
- 빈 문자열 토큰 vs 누락 토큰 모두 발생 가능 → `None` 정규화

## 파이프라인에서의 위치

```
14번 getBidPblancListInfoThngPPSSrch (공고 풀)
       │
       │ bidNtceNo
       ▼
┌──────────────────────────────────────────────────┐
│  본 API (5번)                                     │
│  getOpengResultListInfoThng                       │
│  inqryDiv=4 + bidNtceNo로 개찰결과 조회            │
└──────────────────────────────────────────────────┘
       │
       │ progrsDivCdNm 분기
       │
       ├─ '유찰'    ──► 공급망 빈약 플래그 (mart_item_density 입력)
       │
       ├─ '개찰완료' ──► 1번 API (getScsbidListSttusThng)로
       │                최종 낙찰자 BRN 확정
       │
       └─ '재입찰'   ──► 다음 차수(bidNtceOrd+1) 결과 다시 조회
```

### 분석에 직접 쓰이는 핵심 피처

| 응답 필드 / 파생 | 분석 활용 |
|---|---|
| `progrsDivCdNm` | 유찰률 = 유찰 건수 / 전체 개찰 건수 (품목별·기관별 집계) |
| `prtcptCnum` | 평균 참가업체수 → 품목별 공급망 밀도 (`mart_item_density.density_score`) |
| `opengCorpInfo`의 BRN | 1번 API가 미수신/지연된 공고에서 BRN 1차 확보 (보조 출처) |
| `opengCorpInfo`의 투찰율 | 1번의 `sucsfbidRate`와 비교해 협상 거래 식별 (둘 차이가 크면 협상) |
| `rsrvtnPrceFileExistnceYn` | `Y`인 공고만 9번 API 호출 (불필요한 호출 제거) |
| `dminsttCd` | 한국환경공단 이중 필터 |

## Sample Request

```
http://apis.data.go.kr/1230000/as/ScsbidInfoService/getOpengResultListInfoThng
  ?inqryDiv=4
  &bidNtceNo=R25BK00840922
  &pageNo=1
  &numOfRows=10
  &ServiceKey=인증키
```

## Sample Response (XML)

```xml
<response>
  <header>
    <resultCode>00</resultCode>
    <resultMsg>정상</resultMsg>
  </header>
  <body>
    <items>
      <item>
        <bidNtceNo>R25BK00840922</bidNtceNo>
        <bidNtceOrd>000</bidNtceOrd>
        <bidClsfcNo>1</bidClsfcNo>
        <rbidNo>000</rbidNo>
        <bidNtceNm>근접전자기장 내성 시험 시스템 구축</bidNtceNm>
        <opengDt>2025-06-17 11:00:00</opengDt>
        <prtcptCnum>2</prtcptCnum>
        <opengCorpInfo>이엠테스트코리아 주식회사^1428139282^김종인^178750000^97.992</opengCorpInfo>
        <progrsDivCdNm>개찰완료</progrsDivCdNm>
        <inptDt>2025-07-14 09:57:49</inptDt>
        <rsrvtnPrceFileExistnceYn>Y</rsrvtnPrceFileExistnceYn>
        <ntceInsttCd>1230137</ntceInsttCd>
        <ntceInsttNm>조달청 대구지방조달청</ntceInsttNm>
        <dminsttCd>Z021943</dminsttCd>
        <dminsttNm>대구경북첨단의료산업진흥재단</dminsttNm>
        <opengRsltNtcCntnts></opengRsltNtcCntnts>
      </item>
    </items>
    <numOfRows>10</numOfRows>
    <pageNo>1</pageNo>
    <totalCount>1</totalCount>
  </body>
</response>
```

## TypeScript 타입 (참조 구현)

```ts
// 요청
type InqryDiv = "1" | "2" | "3" | "4";

interface GetOpengResultListInfoThngParams {
  ServiceKey: string;
  numOfRows: number;
  pageNo: number;
  inqryDiv: InqryDiv;
  type?: "json" | "xml";
  /** YYYYMMDDHHMM, inqryDiv=1·2·3일 때 필수 */
  inqryBgnDt?: string;
  inqryEndDt?: string;
  /** inqryDiv=4일 때 필수 */
  bidNtceNo?: string;
}

// 응답 item (raw, caret 분리 전)
interface OpengResultRawItem {
  bidNtceNo: string;
  bidNtceOrd: string;
  bidClsfcNo: string;
  rbidNo: string;
  bidNtceNm: string;
  opengDt: string;                    // YYYY-MM-DD HH:MM:SS
  prtcptCnum: string;                 // 숫자 문자열
  opengCorpInfo: string;              // ⚠️ caret(^) 구분 단일 필드
  progrsDivCdNm: "유찰" | "개찰완료" | "재입찰";
  inptDt: string;
  rsrvtnPrceFileExistnceYn: "Y" | "N" | "";
  ntceInsttCd: string;
  ntceInsttNm: string;
  dminsttCd: string;
  dminsttNm: string;
  opengRsltNtcCntnts: string;
}

// 도메인 변환 (opengCorpInfo 파싱 후)
type OpengCase = "single" | "multiple" | "negotiation" | "empty" | "malformed";

interface OpengCorpInfoParsed {
  case: OpengCase;
  winnerName: string | null;
  brn: string | null;                 // 10자리, 다수 낙찰자/유찰 시 null
  ceoName: string | null;
  bidAmount: number | null;           // 원
  bidRate: number | null;             // %
}

interface OpengResultRecord {
  bidNtceNo: string;
  bidNtceOrd: string;
  bidNtceNm: string;
  opengAt: Date;
  participantCount: number;
  status: "유찰" | "개찰완료" | "재입찰";
  hasReservedPriceFile: boolean;
  corp: OpengCorpInfoParsed;          // 파싱된 업체 정보
  dminsttCd: string;
  dminsttNm: string;
  noticeContent: string | null;
  inputAt: Date | null;
}
```

### 변환 시 주의

- **`opengCorpInfo` 파싱은 무조건 케이스 분기** — 단순 `split("^")`만 하면 다수 낙찰자/협상 케이스에서 잘못된 값 추출
- **`prtcptCnum=0` + `progrsDivCdNm=유찰`** 조합이 진짜 유찰 — 한쪽만 보면 오판 가능
- **재입찰 케이스 처리** — 같은 `bidNtceNo`에 `bidNtceOrd`가 다른 row가 여러 개 올 수 있음. 분석 단위가 (공고, 차수)인지 (공고)인지 결정 필요
- **`opengRsltNtcCntnts` 빈 값 빈번** — 자유 텍스트라 NLP 적용 시 사전 필터링 필수
- **금액·률 타입** — `bidAmount`는 원화 정수(`Number()` 또는 `BigInt()`), `bidRate`는 소수(`97.992`)
- **시간 포맷** — `opengDt`/`inptDt` 모두 19자리 `YYYY-MM-DD HH:MM:SS`

## Error Codes

`_common.md`의 공통 에러코드 표 참조 (`00`/`30`/`99` + 게이트웨이 `OpenAPI_ServiceResponse`).

## 미해결 / 확인 필요

- [ ] `bidNtceNo` size 정의(11) vs 실제 데이터(13자리) 불일치 — 공통 가이드 필요
- [ ] `opengCorpInfo` **다수 낙찰자 케이스의 정확한 토큰 구조** — 실제 응답 샘플로 검증 필요 (몇 개 토큰? 빈 토큰 위치?)
- [ ] `opengCorpInfo` **협상에 의한 계약 케이스의 정확한 포맷** — 후행 빈 토큰? 토큰 자체가 빠지나?
- [ ] `progrsDivCdNm` 외 다른 값 (유찰/개찰완료/재입찰 외) 가능성
- [ ] `rsrvtnPrceFileExistnceYn=Y`인데 9번 API 호출 시 결과 0건인 케이스 가능성
- [ ] `inqryDiv=1·2·3`의 최대 조회 기간 (1개월 윈도우 추정)
- [ ] `numOfRows` 최대값

## 참고

- **연계 API** (모두 같은 `bidNtceNo + bidNtceOrd`로 join):
  - 14번 `getBidPblancListInfoThngPPSSrch` — 공고 메타 (이 API의 입력원)
  - 1번 `getScsbidListSttusThng` — 본 API의 `progrsDivCdNm=개찰완료`인 row의 최종 낙찰자 확정
  - 9번 `getOpengResultListInfoThngPreparPcDetail` — 본 API의 `rsrvtnPrceFileExistnceYn=Y`일 때 복수예가 디테일

- **5번 vs 1번 사용 가이드**:
  - **유찰률·공급망 밀도 분석** → 5번 우선 (유찰 포함)
  - **최종 낙찰자 BRN 확정** → 1번 우선 (정형 필드)
  - **두 결과의 BRN이 다르면** → 협상에 의한 계약 가능성 (5번의 1순위 ≠ 1번의 최종낙찰자)
