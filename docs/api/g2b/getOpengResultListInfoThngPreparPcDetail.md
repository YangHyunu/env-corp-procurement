---
operationId: getOpengResultListInfoThngPreparPcDetail
operationNo: 9
provider: g2b
service: ScsbidInfoService
type: query-list
aliases:
  - 개찰결과
  - 예비가격상세
  - 복수예가
  - 기초예정가격
  - 추첨예가
  - 물품 개찰결과
status: documented
---

# 개찰결과 물품 예비가격상세 목록 조회

`getOpengResultListInfoThngPreparPcDetail`

물품 입찰의 **개찰결과 + 복수예비가격(복수예가) 상세**를 조회한다. 한 입찰공고당 보통 15개의 복수예가 row가 반환되며, 그중 추첨된(`drwtYn=Y`) row들의 평균이 예정가격(`plnprc`) 산정 근거가 된다.

## 메타

| 항목 | 값 |
|---|---|
| operationId | `getOpengResultListInfoThngPreparPcDetail` |
| operationNo | 9 |
| 유형 | 조회(목록) |
| 서비스 | ScsbidInfoService (개찰결과정보) |
| 제공 | 조달청 / NIA 한국정보화진흥원 |
| Callback URL | N/A |
| 최대 메시지 사이즈 | 4000 bytes |
| 평균 응답 시간 | 500 ms |
| 초당 최대 트랜잭션 | 30 TPS |

## Endpoint

```
GET http://apis.data.go.kr/1230000/as/ScsbidInfoService/getOpengResultListInfoThngPreparPcDetail
```

> ⚠️ 운영 환경에서는 `https`로 시도 후 실패 시 `http` fallback 권장. 공공데이터포털 게이트웨이는 일부 서비스가 http만 지원함.

## Request Parameters

| name | ko | required | size | sample | note |
|---|---|---|---|---|---|
| `ServiceKey` | 서비스키 | ✅ | 400 | (인증키) | 공공데이터포털 발급. URL 인코딩 필수 |
| `numOfRows` | 한 페이지 결과 수 | ❌ | 4 | 10 | 1건 입찰의 복수예가가 15개이므로 15 이상 권장 |
| `pageNo` | 페이지 번호 | ❌ | 4 | 1 | |
| `inqryDiv` | 조회구분 | ✅ | 1 | 1 | `1`=입력일시 / `2`=입찰공고번호 |
| `type` | 응답 타입 | ❌ | 4 | `json` | 생략 시 XML. JSON 원하면 `json` 명시 |
| `inqryBgnDt` | 조회시작일시 | 조건부 | 12 | `202507010000` | `YYYYMMDDHHMM`. `inqryDiv=1`일 때 필수 |
| `inqryEndDt` | 조회종료일시 | 조건부 | 12 | `202507012359` | `YYYYMMDDHHMM`. `inqryDiv=1`일 때 필수 |
| `bidNtceNo` | 입찰공고번호 | 조건부 | 11 | `R25BK0084502` | `inqryDiv=2`일 때 필수. 차세대 13자리 체계는 추가 검증 필요 |
| `bidNtceOrd` | 입찰공고차수 | ❌ | 3 | `000` | 명세표엔 없으나 sample URI에서 사용됨 — 옵션 가능 |

> **주의**: 명세서상 `bidNtceNo`의 size는 `11`이지만, 응답 데이터의 실제 입찰공고번호는 13자리(`R25BK00845027`)다. 차세대 나라장터 번호체계(R+년도2+단계구분2+순번8 = 총 13자리)와 명세서 size 정의 사이에 불일치가 있으니 13자리로 보내고 안 되면 11자리로 잘라서 재시도하는 식으로 방어 코드 작성 권장.

### 호출 규칙 (에이전트용)

`inqryDiv` 값에 따라 필수 파라미터가 달라진다:

| `inqryDiv` | 의미 | 필수 추가 파라미터 |
|---|---|---|
| `1` | 입력일시 기준 조회 | `inqryBgnDt`, `inqryEndDt` |
| `2` | 입찰공고번호 기준 조회 | `bidNtceNo` |

- 일시 포맷은 **요청은 `YYYYMMDDHHMM`(12자리)**, **응답은 `YYYY-MM-DD HH:MM:SS`(19자리)** — 헷갈리지 말 것
- `ServiceKey`는 환경변수(`PROCUREMENT_API_KEY`)로 관리하고 코드에 하드코딩 금지
- 1건의 입찰공고에 대해 보통 **15개 row**가 반환됨 → `numOfRows=15` 또는 그 이상으로 잡고 `totalCount`로 페이징 결정
- `inqryDiv=1`로 기간 조회 시 응답이 매우 클 수 있음. 1일 단위로 쪼개서 호출하는 것을 권장

## Response Parameters

응답은 `<response><header/><body><items><item/>...</items></body></response>` 구조의 XML(또는 `type=json` 시 JSON).

### Header

| name | ko | size | required | note |
|---|---|---|---|---|
| `resultCode` | 결과코드 | 2 | ✅ | 정상 시 `00` |
| `resultMsg` | 결과메시지 | 50 | ✅ | 정상 시 `정상` |

### Body (페이지 메타)

| name | ko | size | sample | note |
|---|---|---|---|---|
| `numOfRows` | 한 페이지 결과 수 | 4 | 10 | 요청한 값 echo |
| `pageNo` | 페이지 번호 | 4 | 1 | 요청한 값 echo |
| `totalCount` | 데이터 총 개수 | 4 | 17 | 전체 매칭 row 수. 페이징 분기에 사용 |

### Body > items > item

| name | ko | size | required | sample | note |
|---|---|---|---|---|---|
| `bidNtceNo` | 입찰공고번호 | 11 | ✅ | `R25BK00845027` | 차세대 나라장터 13자리 (R+년도2+단계구분2+순번8). 단계구분: `BK`=입찰, `TA`=계약, `DD`=발주계획, `BD`=사전규격 |
| `bidNtceOrd` | 입찰공고차수 | 3 | ✅ | `000` | 재공고/재입찰 발생 시 증가 |
| `bidClsfcNo` | 입찰분류번호 | 5 | ✅ | `1` | 동일 공고번호 내 집행일련번호 |
| `rbidNo` | 재입찰번호 | 3 | ✅ | `000` | |
| `bidNtceNm` | 입찰공고명 | 1000 | ✅ | `CT 및 X-ray 구매` | |
| `plnprc` | 예정가격 | 21 | ❌ | `270648500` | (원화) 낙찰자 선정 기준 가격이자 계약체결 최고 상한. **추첨된 복수예가의 평균** |
| `bssamt` | 기초금액 | 21 | ❌ | `270499000` | (원화) 거래실례가격·원가계산가격 등으로 산정한 기준 금액 |
| `totRsrvtnPrceNum` | 총예가건수 | 2 | ❌ | `15` | 보통 15개 (복수예가 풀 사이즈) |
| `compnoRsrvtnPrceSno` | 복수예가순번 | 6 | ❌ | `7` | 1 ~ `totRsrvtnPrceNum` 범위 |
| `bsisPlnprc` | 기초예정가격 | 21 | ❌ | `265727400` | (원화) 이 row 한 건의 예정가격 후보값 |
| `drwtYn` | 추첨여부 | 1 | ✅ | `Y` | `Y`/`N`. 추첨된 row들의 `bsisPlnprc` 평균이 `plnprc` |
| `drwtNum` | 추첨횟수 | 22 | ❌ | `1` | |
| `bidwinrSlctnAplBssCntnts` | 최종낙찰자선정적용기준내용 | 200 | ❌ | `조달청` | |
| `rlOpengDt` | 실개찰일시 | 19 | ❌ | `2025-07-01 11:07:08` | `YYYY-MM-DD HH:MM:SS` |
| `bssamtBssUpNum` | 기초금액기준상위건수 | 2 | ❌ | `8` | |
| `compnoRsrvtnPrceMkngDt` | 복수예비가격작성일시 | 19 | ❌ | `2015-11-05 16:28:28` | `YYYY-MM-DD HH:MM:SS` |
| `inptDt` | 입력일시 | 19 | ✅ | `2025-07-01 11:07:08` | `YYYY-MM-DD HH:MM:SS`. `inqryDiv=1`의 검색 기준 |
| `PrearngPrcePurcnstcst` | 예정가격순공사원가 | 22 | ❌ | `0` | 재료비·노무비·경비·부가세 합산. 물품에선 보통 빈 값 또는 `0` |

> **항목구분 표기**: ✅ = 필수(1), ❌ = 옵션(0). 명세서 원문 표기 — 필수(1) / 옵션(0) / 1건 이상 복수건(1..n) / 0건 또는 복수건(0..n).

## 도메인 컨텍스트 (중요)

이 API는 단순 조회처럼 보이지만, 실제로는 **복수예비가격(복수예가) 추첨 시스템의 결과**를 반환한다. 에이전트가 코드 짤 때 이 모델을 이해하고 있어야 함:

1. **1건의 입찰공고 → N개의 기초예정가격 후보**가 사전에 작성됨 (`totRsrvtnPrceNum`, 보통 15개).
2. 각 후보는 row 1개로 반환되며, `compnoRsrvtnPrceSno` 1, 2, ..., 15로 식별됨.
3. 개찰 시점에 **참가 업체들이 이 후보 풀에서 무작위 추첨** → 추첨된 row는 `drwtYn=Y`.
4. **추첨된 row들의 `bsisPlnprc` 평균이 최종 `plnprc`(예정가격)**.
5. 따라서 `bidNtceNo` 단위로 grouping해서 처리해야 의미가 있다 — 단순 row 나열은 분석 가치 없음.

```
1 입찰공고 (bidNtceNo)
├─ 복수예가 #1  bsisPlnprc=268,378,300  drwtYn=N
├─ 복수예가 #2  bsisPlnprc=273,106,700  drwtYn=N
├─ 복수예가 #3  bsisPlnprc=267,875,200  drwtYn=N
├─ 복수예가 #4  bsisPlnprc=269,928,300  drwtYn=Y  ← 추첨됨
├─ 복수예가 #5  bsisPlnprc=274,583,600  drwtYn=Y  ← 추첨됨
├─ 복수예가 #6  bsisPlnprc=275,706,200  drwtYn=N
├─ 복수예가 #7  bsisPlnprc=265,727,400  drwtYn=Y  ← 추첨됨
├─ ...
└─ 복수예가 #15
                                        ↓
                            plnprc = 270,648,500 (원)
                            (= 추첨 row들의 평균)
```

## Sample Request

```
http://apis.data.go.kr/1230000/as/ScsbidInfoService/getOpengResultListInfoThngPreparPcDetail
  ?inqryDiv=2
  &bidNtceNo=R25BK00845027
  &bidNtceOrd=000
  &pageNo=1
  &numOfRows=15
  &ServiceKey=인증키
```

## Sample Response (XML, 일부 발췌)

```xml
<response>
  <header>
    <resultCode>00</resultCode>
    <resultMsg>정상</resultMsg>
  </header>
  <body>
    <items>
      <item>
        <bidNtceNo>R25BK00845027</bidNtceNo>
        <bidNtceOrd>000</bidNtceOrd>
        <bidClsfcNo>1</bidClsfcNo>
        <rbidNo>000</rbidNo>
        <bidNtceNm>CT 및 X-ray 구매</bidNtceNm>
        <plnprc>270648500</plnprc>
        <bssamt>270499000</bssamt>
        <totRsrvtnPrceNum>15</totRsrvtnPrceNum>
        <compnoRsrvtnPrceSno>4</compnoRsrvtnPrceSno>
        <bsisPlnprc>269928300</bsisPlnprc>
        <drwtYn>Y</drwtYn>
        <drwtNum>1</drwtNum>
        <bidwinrSlctnAplBssCntnts>조달청</bidwinrSlctnAplBssCntnts>
        <rlOpengDt>2025-07-01 11:07:08</rlOpengDt>
        <bssamtBssUpNum>8</bssamtBssUpNum>
        <compnoRsrvtnPrceMkngDt>2025-07-01 10:47:30</compnoRsrvtnPrceMkngDt>
        <inptDt>2025-07-01 11:07:08</inptDt>
        <PrearngPrcePurcnstcst></PrearngPrcePurcnstcst>
      </item>
      <!-- ... 나머지 14건 (compnoRsrvtnPrceSno 1~15) ... -->
    </items>
    <numOfRows>10</numOfRows>
    <pageNo>1</pageNo>
    <totalCount>15</totalCount>
  </body>
</response>
```

## TypeScript 타입 (참조 구현)

```ts
// 요청
type InqryDiv = "1" | "2";

interface GetOpengResultListInfoThngPreparPcDetailParams {
  ServiceKey: string;
  numOfRows?: number;
  pageNo?: number;
  inqryDiv: InqryDiv;
  type?: "json";
  /** YYYYMMDDHHMM, inqryDiv=1일 때 필수 */
  inqryBgnDt?: string;
  /** YYYYMMDDHHMM, inqryDiv=1일 때 필수 */
  inqryEndDt?: string;
  /** inqryDiv=2일 때 필수 */
  bidNtceNo?: string;
  bidNtceOrd?: string;
}

// 응답 (item 단위)
interface PreparPcDetailItem {
  bidNtceNo: string;          // 입찰공고번호
  bidNtceOrd: string;         // 입찰공고차수
  bidClsfcNo: string;         // 입찰분류번호
  rbidNo: string;             // 재입찰번호
  bidNtceNm: string;          // 입찰공고명
  plnprc: string;             // 예정가격 (숫자 문자열, 원)
  bssamt: string;             // 기초금액 (숫자 문자열, 원)
  totRsrvtnPrceNum: string;   // 총예가건수
  compnoRsrvtnPrceSno: string;// 복수예가순번
  bsisPlnprc: string;         // 기초예정가격 (숫자 문자열, 원)
  drwtYn: "Y" | "N";          // 추첨여부
  drwtNum: string;            // 추첨횟수
  bidwinrSlctnAplBssCntnts: string;
  rlOpengDt: string;          // YYYY-MM-DD HH:MM:SS
  bssamtBssUpNum: string;
  compnoRsrvtnPrceMkngDt: string; // YYYY-MM-DD HH:MM:SS
  inptDt: string;             // YYYY-MM-DD HH:MM:SS
  PrearngPrcePurcnstcst: string | "";
}

interface PreparPcDetailResponse {
  response: {
    header: { resultCode: string; resultMsg: string };
    body: {
      items: { item: PreparPcDetailItem[] };
      numOfRows: number;
      pageNo: number;
      totalCount: number;
    };
  };
}

// 도메인 변환 헬퍼 (권장)
interface BidPreparPriceGroup {
  bidNtceNo: string;
  bidNtceNm: string;
  plnprc: number;             // 예정가격
  bssamt: number;              // 기초금액
  totRsrvtnPrceNum: number;
  rlOpengDt: Date;
  candidates: Array<{
    sno: number;               // 복수예가 순번 (1..N)
    bsisPlnprc: number;
    drawn: boolean;            // drwtYn === "Y"
  }>;
}
```

### 변환 시 주의

- 모든 금액 필드(`plnprc`, `bssamt`, `bsisPlnprc`)는 **문자열로 옴** → `Number()` 또는 `BigInt()`로 명시적 변환. 21자리까지 허용되므로 매우 큰 금액은 BigInt 고려.
- `compnoRsrvtnPrceSno`도 문자열 — 정렬 시 `parseInt` 후 정렬할 것 (`"10"` < `"2"` 문제 방지).
- `PrearngPrcePurcnstcst`는 빈 문자열로 올 수 있음 → `null` 또는 `0`으로 정규화 권장.
- 응답이 단일 `item`인 경우 일부 XML 파서가 **배열이 아닌 객체**로 반환할 수 있음 — 항상 배열로 정규화하는 헬퍼 사용 권장.

## Error Codes

> ⚠️ 본 명세서에는 에러코드 표가 없음. 공공데이터포털 공통 에러코드를 따른다고 가정. 별도 확인 필요.

일반적으로 다음과 같은 코드를 만남:

| resultCode | 의미 | 대응 |
|---|---|---|
| `00` | 정상 | — |
| `30` | 서비스키 등록 안 됨 | 활용신청 상태 확인 |
| `99` | 기타 오류 | 재시도 + 로깅 |
| (HTTP 오류) | 게이트웨이 자체 오류 | 메시지 본문에 `OpenAPI_ServiceResponse` XML로 옴, 별도 파싱 |

`OpenAPI_ServiceResponse` 형태의 게이트웨이 에러도 처리해야 함:

```xml
<OpenAPI_ServiceResponse>
  <cmmMsgHeader>
    <errMsg>SERVICE ERROR</errMsg>
    <returnAuthMsg>SERVICEKEY_TYPE_ERROR</returnAuthMsg>
    <returnReasonCode>30</returnReasonCode>
  </cmmMsgHeader>
</OpenAPI_ServiceResponse>
```

## 미해결 / 확인 필요

- [ ] `bidNtceNo` size 정의(11) vs 실제 데이터(13자리) 불일치 — 자체 가이드 확정 필요
- [ ] `bidNtceOrd` 요청 파라미터로 받는지 명세서엔 없음, sample URI에만 있음 — 실제 호출로 검증
- [ ] 정식 에러코드 표 — 별도 공통 명세 페이지 확인 필요
- [ ] `inqryDiv=1` 사용 시 최대 조회 기간 제한 — 1개월? 1주일? 별도 확인
- [ ] 페이징 최대 `numOfRows` 한계값 (보통 999 또는 9999)

## 참고

- 같은 서비스(`ScsbidInfoService`)의 다른 오퍼레이션과 함께 사용하면 더 풍부한 분석 가능:
  - 16번 `getScsbidListSttusThngPPSSrch` — 낙찰자 목록(누가 얼마에 낙찰)
  - 본 9번 `getOpengResultListInfoThngPreparPcDetail` — 예정가격 산정 근거 (복수예가 풀)
  - → join key는 `bidNtceNo` + `bidNtceOrd`
