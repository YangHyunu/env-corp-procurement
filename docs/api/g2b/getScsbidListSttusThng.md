---
operationId: getScsbidListSttusThng
operationNo: 1
provider: g2b
service: ScsbidInfoService
type: query-list
role: brn-source
aliases:
  - 낙찰
  - 낙찰자
  - 낙찰업체
  - 낙찰목록
  - 사업자등록번호
  - BRN
  - 최종낙찰자
  - 낙찰금액
related:
  - getScsbidListSttusThngPPSSrch  # 16번 — 검색조건 확장판
status: documented
---

# 낙찰된 목록 현황 물품조회

`getScsbidListSttusThng`

물품 입찰의 **최종 낙찰자 정보**를 조회한다. 분석 파이프라인의 **BRN(사업자등록번호) 1차 출처** — 14번 공고 API로 모은 `bidNtceNo`를 이 API에 던지면 낙찰업체 BRN, 명, 대표자, 주소, 낙찰금액·낙찰률이 한 번에 들어온다.

## 메타

| 항목 | 값 |
|---|---|
| operationId | `getScsbidListSttusThng` |
| operationNo | 1 |
| 유형 | 조회(목록) |
| 서비스 | ScsbidInfoService (낙찰정보) |
| 제공 | 조달청 / NIA 한국정보화진흥원 |
| Callback URL | N/A |
| 최대 메시지 사이즈 | 4000 bytes |
| 평균 응답 시간 | 500 ms |
| 초당 최대 트랜잭션 | 30 TPS |

## ⚠️ 16번 PPSSrch 변형과의 차이

같은 서비스에 비슷한 이름의 변형판이 존재한다 — **둘은 다른 API다**:

| 구분 | **본 API (1번)** | 16번 (`...PPSSrch`) |
|---|---|---|
| operationId | `getScsbidListSttusThng` | `getScsbidListSttusThngPPSSrch` |
| `inqryDiv` 옵션 | 1=등록일시 / 2=공고일시 / 3=개찰일시 / **4=입찰공고번호** | 1=공고게시일시 / 2=개찰일시 / 3=입찰공고번호 |
| 추가 검색 조건 | 없음 (단순) | 참가업체수·낙찰업체명·BRN·낙찰률 등으로 검색 가능 |
| 응답 필드 수 | 약 20개 (가벼움) | 더 많음 |
| 권장 용도 | **`bidNtceNo` → 낙찰자 변환** (1:N 룩업) | 자유 조건 검색 |

분석 파이프라인에서는 보통 **본 1번 API를 사용**(공고 풀에서 BRN으로 가는 가장 빠른 경로)한다.

## Endpoint

```
GET http://apis.data.go.kr/1230000/as/ScsbidInfoService/getScsbidListSttusThng
```

## Request Parameters

| name | ko | required | size | sample | note |
|---|---|---|---|---|---|
| `ServiceKey` | 서비스키 | ✅ | 400 | (인증키) | 공공데이터포털 발급. URL 인코딩 필수 |
| `numOfRows` | 한 페이지 결과 수 | ✅ | 4 | 10 | |
| `pageNo` | 페이지 번호 | ✅ | 4 | 1 | |
| `inqryDiv` | 조회구분 | ✅ | 1 | 1 | `1`=등록일시 / `2`=공고일시 / `3`=개찰일시 / `4`=입찰공고번호 |
| `type` | 응답 타입 | ❌ | 4 | `json` | 생략 시 XML, `json` 명시 시 JSON |
| `inqryBgnDt` | 조회시작일시 | 조건부 | 12 | `202507010000` | `YYYYMMDDHHMM`. `inqryDiv=1·2·3`일 때 필수 |
| `inqryEndDt` | 조회종료일시 | 조건부 | 12 | `202507012359` | 동상 |
| `bidNtceNo` | 입찰공고번호 | 조건부 | 40 | `R25BK00965123` | `inqryDiv=4`일 때 필수. 실제 데이터는 13자리 |

## 호출 규칙 (에이전트용)

### `inqryDiv` 분기

| `inqryDiv` | 의미 | 필수 추가 파라미터 | 권장 용도 |
|---|---|---|---|
| `1` | 등록일시 (낙찰 등록 시점) | `inqryBgnDt`, `inqryEndDt` | 어제 등록된 낙찰 증분 수집 |
| `2` | 공고일시 (입찰공고 게시 시점) | `inqryBgnDt`, `inqryEndDt` | 공고일 기준 분석 |
| `3` | 개찰일시 | `inqryBgnDt`, `inqryEndDt` | 개찰일 기준 분석 |
| `4` | 입찰공고번호 | `bidNtceNo` | **공고 풀 → BRN 룩업 시 사용** |

### 분석 파이프라인 표준 호출 패턴

```python
# 14번 API에서 얻은 bidNtceNo 풀을 순회하면서 낙찰자 조회
for bid_ntce_no in bid_ntce_no_pool:  # from getBidPblancListInfoThngPPSSrch
    rows = get_scsbid_list(
        inqryDiv=4,
        bidNtceNo=bid_ntce_no,
        numOfRows=999,
        pageNo=1,
    )
    # rows[*].bidwinnrBizno → BRN 추출 → SR 인증 / 부정당제재 API에 전달
```

또는 일별 증분 수집:

```python
# 매일 새벽: 어제 등록된 낙찰 전체 수집
get_scsbid_list(
    inqryDiv=1,
    inqryBgnDt=f"{yesterday}0000",
    inqryEndDt=f"{yesterday}2359",
    numOfRows=999,
    pageNo=1,
)
```

### 페이징
- `inqryDiv=4`는 보통 1~수 건이라 페이징 거의 불필요 (한 공고에 낙찰자 1명이 일반적)
- `inqryDiv=1·2·3`은 기간에 따라 수천~수만 건 가능 → `totalCount`로 페이징

## Response Parameters

응답은 `<response><header/><body><items><item/>...</items></body></response>` 구조의 XML(또는 `type=json` 시 JSON).

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
| `bidNtceNo` | 입찰공고번호 | 40 | ✅ | `R25BK00965123` | 차세대 13자리(R+년도2+단계구분2+순번8). **size 정의 vs 실제 불일치(40 vs 13)** |
| `bidNtceOrd` | 입찰공고차수 | 3 | ✅ | `000` | 재공고/재입찰 발생 시 증가 |
| `bidClsfcNo` | 입찰분류번호 | 5 | ✅ | `1` | 동일 공고번호 내 집행일련번호 |
| `rbidNo` | 재입찰번호 | 3 | ✅ | `000` | |
| `ntceDivCd` | 공고구분코드 | 7 | ✅ | `통050001` | `통050001`=조달청 또는 나라장터 자체 공고건 |
| `bidNtceNm` | 입찰공고명 | 1000 | ✅ | `혁신육아복합센터 건립공사(기계) 관급자재(간접가열보일러)` | |

### item — 낙찰업체 정보 ⭐

이 섹션이 **분석의 핵심**. 모든 SR/제재/업체 메타 API의 조인 키 BRN이 여기서 나온다.

| name | ko | size | required | sample | note |
|---|---|---|---|---|---|
| `bidwinnrNm` | 최종낙찰업체명 | 200 | ✅ | `주식회사 동광보일러` | 정규화 시 `(주)`/`주식회사` 통일 권장 |
| `bidwinnrBizno` | 최종낙찰업체사업자등록번호 | 10 | ✅ | `1408121883` | **BRN — 모든 SR 데이터셋의 조인 키**. 하이픈 제거된 10자리 |
| `bidwinnrCeoNm` | 최종낙찰업체대표자명 | 35 | ✅ | `박정연` | |
| `bidwinnrAdrs` | 최종낙찰업체주소 | 200 | ❌ | `충청남도 아산시 수장로 67-0 (배미동)` | |
| `bidwinnrTelNo` | 최종낙찰업체전화번호 | 25 | ❌ | `02-6258-8989` | **핸드폰번호는 `*`로 마스킹**되어 옴 |

### item — 낙찰 결과

| name | ko | size | required | sample | note |
|---|---|---|---|---|---|
| `prtcptCnum` | 참가업체수 | 6 | ❌ | `2` | 입찰 경쟁률 분석 피처로 활용 |
| `sucsfbidAmt` | 최종낙찰금액 | 21 | ❌ | `83500000` | (원화). 협상 등을 거친 최종 낙찰액 |
| `sucsfbidRate` | 최종낙찰률 | 18 | ❌ | `97.82` | 최종낙찰금액 / 예정가격 × 100 (%) |
| `rlOpengDt` | 실개찰일시 | 19 | ❌ | `2025-07-23 11:00:00` | `YYYY-MM-DD HH:MM:SS` |
| `fnlSucsfDate` | 최종낙찰일자 | 10 | ❌ | `2025-07-23` | `YYYY-MM-DD` (시각 없음) |
| `fnlSucsfCorpOfcl` | 최종낙찰업체담당자 | 35 | ❌ | | (응답 샘플에선 빈 값) |

### item — 수요기관 / 등록 메타

| name | ko | size | required | sample | note |
|---|---|---|---|---|---|
| `dminsttCd` | 수요기관코드 | 7 | ❌ | `6280147` | **한국환경공단 필터 시 핵심**. 행자부코드 우선 |
| `dminsttNm` | 수요기관명 | 200 | ❌ | `인천광역시 종합건설본부` | |
| `rgstDt` | 등록일시 | 19 | ✅ | `2025-07-23 15:20:05` | `YYYY-MM-DD HH:MM:SS`. `inqryDiv=1`의 검색 기준 |

> **항목구분**: ✅ 필수(1), ❌ 옵션(0).

## 파이프라인에서의 위치

이 API는 **"공고 → BRN" 변환의 핵심 노드**. 14번에서 시작한 흐름이 여기서 BRN으로 분기된다.

```
14번 getBidPblancListInfoThngPPSSrch
       │
       │ bidNtceNo (1..N)
       ▼
┌────────────────────────────────────┐
│  본 API (1번)                       │
│  getScsbidListSttusThng             │
│  inqryDiv=4 + bidNtceNo로 1:N 룩업  │
└────────────────────────────────────┘
       │
       │ bidwinnrBizno (BRN, 10자리)
       │ + bidwinnrNm, bidwinnrCeoNm, bidwinnrAdrs
       │ + sucsfbidAmt, sucsfbidRate, prtcptCnum
       ▼
┌────────────────────────────────────────────────┐
│  BRN 풀 (분석 단위)                              │
│                                                │
│  ├─► getPrcrmntCorpInfo (업체 메타)              │
│  ├─► 공공구매 인증서 (중소·여성·장애인·사회적기업) │
│  ├─► 장애인 표준사업장 (KEAD)                    │
│  ├─► 창업기업확인서 (KISED)                      │
│  ├─► 자활용사촌·복지공장 (보훈부)                 │
│  └─► 부정당제재 정보                             │
└────────────────────────────────────────────────┘
       │
       │ + 9번 getOpengResultListInfoThngPreparPcDetail
       │   (같은 bidNtceNo로 복수예가 디테일)
       ▼
   mart_company_sr / mart_item_supply
```

### 분석에 직접 쓰이는 핵심 피처

| 응답 필드 | 분석 활용 |
|---|---|
| `bidwinnrBizno` | **BRN 조인 키** — 모든 SR/제재/업체 데이터셋의 통합 키 |
| `bidwinnrNm` | 업체명 정규화 후 SR 인증 매칭 보조키 (BRN 결측 시 fallback) |
| `bidwinnrAdrs` | 지역별 SR 군집 분석 (광역시도 추출) |
| `sucsfbidAmt` | 업체별 누적 낙찰액 → 안정성·규모 피처 |
| `sucsfbidRate` | 낙찰률 분포 → 경쟁력 피처 |
| `prtcptCnum` | 입찰 경쟁률 → 품목별 공급망 밀도 보조 지표 |
| `dminsttCd` | 한국환경공단 필터 (14번에서 못 걸렀다면 여기서 이중 필터) |

## Sample Request

```
http://apis.data.go.kr/1230000/as/ScsbidInfoService/getScsbidListSttusThng
  ?inqryDiv=4
  &bidNtceNo=R25BK00965123
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
        <bidNtceNo>R25BK00965123</bidNtceNo>
        <bidNtceOrd>000</bidNtceOrd>
        <bidClsfcNo>1</bidClsfcNo>
        <rbidNo>000</rbidNo>
        <ntceDivCd>통050001</ntceDivCd>
        <bidNtceNm>혁신육아복합센터 건립공사(기계) 관급자재(간접가열보일러)</bidNtceNm>
        <prtcptCnum>2</prtcptCnum>
        <bidwinnrNm>주식회사 동광보일러</bidwinnrNm>
        <bidwinnrBizno>1408121883</bidwinnrBizno>
        <bidwinnrCeoNm>박정연</bidwinnrCeoNm>
        <bidwinnrAdrs>충청남도 아산시 수장로 67-0 (배미동)</bidwinnrAdrs>
        <bidwinnrTelNo>02-6258-8989</bidwinnrTelNo>
        <sucsfbidAmt>83500000</sucsfbidAmt>
        <sucsfbidRate>97.82</sucsfbidRate>
        <rlOpengDt>2025-07-23 11:00:00</rlOpengDt>
        <dminsttCd>6280147</dminsttCd>
        <dminsttNm>인천광역시 종합건설본부</dminsttNm>
        <rgstDt>2025-07-23 15:20:05</rgstDt>
        <fnlSucsfDate>2025-07-23</fnlSucsfDate>
        <fnlSucsfCorpOfcl></fnlSucsfCorpOfcl>
      </item>
    </items>
    <numOfRows>999</numOfRows>
    <pageNo>1</pageNo>
    <totalCount>1</totalCount>
  </body>
</response>
```

## TypeScript 타입 (참조 구현)

```ts
// 요청
type InqryDiv = "1" | "2" | "3" | "4";

interface GetScsbidListSttusThngParams {
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

// 응답 item
interface ScsbidListItem {
  // 공고 식별자
  bidNtceNo: string;
  bidNtceOrd: string;
  bidClsfcNo: string;
  rbidNo: string;
  ntceDivCd: string;
  bidNtceNm: string;

  // 낙찰업체 (BRN 출처)
  bidwinnrNm: string;
  bidwinnrBizno: string;     // 10자리 BRN
  bidwinnrCeoNm: string;
  bidwinnrAdrs: string;
  bidwinnrTelNo: string;     // 핸드폰은 "*"로 마스킹

  // 낙찰 결과
  prtcptCnum: string;        // 숫자 문자열
  sucsfbidAmt: string;       // 숫자 문자열, 원
  sucsfbidRate: string;      // 숫자 문자열, %
  rlOpengDt: string;         // YYYY-MM-DD HH:MM:SS
  fnlSucsfDate: string;      // YYYY-MM-DD
  fnlSucsfCorpOfcl: string;

  // 수요기관 / 등록
  dminsttCd: string;
  dminsttNm: string;
  rgstDt: string;            // YYYY-MM-DD HH:MM:SS
}

interface ScsbidListResponse {
  response: {
    header: { resultCode: string; resultMsg: string };
    body: {
      items: { item: ScsbidListItem[] };
      numOfRows: number;
      pageNo: number;
      totalCount: number;
    };
  };
}

// 도메인 변환 — BRN 중심 정규화
interface AwardRecord {
  bidNtceNo: string;
  bidNtceOrd: string;
  bidNtceNm: string;
  brn: string;                  // 정규화된 BRN (하이픈 제거 10자리)
  winnerName: string;            // 정규화된 업체명
  winnerCeo: string;
  winnerAddr: string | null;
  region: string | null;         // bidwinnrAdrs에서 추출한 광역시도
  awardAmount: number;           // 원
  awardRate: number;             // %
  participantCount: number | null;
  realOpenAt: Date | null;
  finalAwardDate: Date | null;
  registeredAt: Date;
  dminsttCd: string;
  dminsttNm: string;
}
```

### 변환 시 주의

- **`bidwinnrBizno`는 이미 10자리 하이픈 없는 형태로 옴** — 명세상 size=10. 다른 데이터셋에서 `123-45-67890` 형태로 들어오는 경우 통일 정규화 필요 (`_common.md`의 `normalize_brn` 참조).
- **`bidwinnrTelNo` 마스킹** — 핸드폰번호는 `*`로 옴. 분석에 쓰지 않으면 무시. 쓴다면 `*` 검출해서 `null`로 정규화.
- **`bidwinnrAdrs`에서 지역 추출** — 광역시도 코드 매핑 시 첫 토큰 사용 (`충청남도 아산시...` → `충남`/`44`). 14번 API의 `prtcptLmtRgnCd`와 매핑 필요.
- **금액·률 모두 문자열** — `sucsfbidAmt` (원, 21자리 가능 → BigInt 고려), `sucsfbidRate` (%, 소수 포함).
- **시간 포맷** — `rlOpengDt`/`rgstDt`는 19자리 `YYYY-MM-DD HH:MM:SS`, `fnlSucsfDate`는 10자리 `YYYY-MM-DD` (시각 없음). 파서 분기.
- **빈 문자열** — 옵션 필드들이 미입력 시 `""`로 옴 → `null` 정규화.
- **`bidwinnrNm` 정규화** — `(주)` / `주식회사` / `(유)` / `유한회사` / 후행 공백 제거 후 lowercase 통일. SR API 매칭 시 BRN이 없으면 이게 fallback 키.

## Error Codes

`_common.md`의 공통 에러코드 표 참조 (`00`/`30`/`99` + 게이트웨이 `OpenAPI_ServiceResponse`).

## 미해결 / 확인 필요

- [ ] `bidNtceNo` size 정의(40) vs 실제 데이터(13자리) 불일치 — 공통 가이드 필요
- [ ] `inqryDiv=1·2·3` 사용 시 최대 조회 기간 제한 — 1개월 윈도우 추정 (낙찰·예가 API 표준 제약)
- [ ] `numOfRows` 최대값 (응답 샘플에 999가 보임 → 999가 상한일 가능성)
- [ ] 같은 `bidNtceNo`에 낙찰자가 여러 명 나올 수 있는지 (분할 낙찰·다수공급) — 1:N 처리 검증
- [ ] `ntceDivCd` 코드값 전체 목록 — `통050001` 외 다른 값 확인 필요
- [ ] `bidwinnrTelNo` 마스킹 규칙 — `*` 단일인지 `***`인지 확인

## 참고

- **연계 API** (모두 같은 `bidNtceNo`로 join):
  - 14번 `getBidPblancListInfoThngPPSSrch` — 공고 메타 (이 API의 입력원)
  - 9번 `getOpengResultListInfoThngPreparPcDetail` — 본 공고의 복수예가 풀
  - 16번 `getScsbidListSttusThngPPSSrch` — 동일 도메인의 검색조건 확장 변형
- **BRN 후속 연계**:
  - `getPrcrmntCorpInfo` — 업체 기본 메타 (업종·등록일·주소 정확화)
  - 공공구매 인증서 / 장애인 표준사업장 / 창업기업확인서 / 자활용사촌 / 사회적기업 — SR 인증 매트릭스
  - 부정당제재 정보 — 리스크 플래그
