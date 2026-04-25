---
operationId: getBidPblancListInfoThngPPSSrch
operationNo: 14
provider: g2b
service: BidPublicInfoService
type: query-list
role: seed-api
aliases:
  - 입찰공고
  - 입찰공고조회
  - 물품공고
  - 나라장터 입찰공고
  - 공고검색
  - 세부품명번호 조회
status: documented
---

# 나라장터검색조건에 의한 입찰공고물품조회

`getBidPblancListInfoThngPPSSrch`

물품 입찰공고를 검색조건(공고게시일시·개찰일시·기관·세부품명번호·추정가격 등)으로 조회한다. **분석 파이프라인의 출발점(seed)** — 여기서 얻은 `bidNtceNo`와 `dtilPrdctClsfcNo`로 후속 낙찰·개찰결과 API를 호출하고, `dminsttCd`로 수요기관(예: 한국환경공단)을 필터링한다.

## 메타

| 항목 | 값 |
|---|---|
| operationId | `getBidPblancListInfoThngPPSSrch` |
| operationNo | 14 |
| 유형 | 조회(목록) |
| 서비스 | BidPublicInfoService (입찰공고정보) |
| 제공 | 조달청 / NIA 한국정보화진흥원 |
| Callback URL | N/A |
| 최대 메시지 사이즈 | 4000 bytes |
| 평균 응답 시간 | 500 ms |
| 초당 최대 트랜잭션 | 30 TPS |

## Endpoint

```
GET http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoThngPPSSrch
```

## Request Parameters

| name | ko | required | size | sample | note |
|---|---|---|---|---|---|
| `ServiceKey` | 서비스키 | ✅ | 400 | (인증키) | 공공데이터포털 발급. URL 인코딩 필수 |
| `numOfRows` | 한 페이지 결과 수 | ✅ | 4 | 10 | 최대값은 게이트웨이 정책에 따름 (보통 999) |
| `pageNo` | 페이지 번호 | ✅ | 4 | 1 | |
| `inqryDiv` | 조회구분 | ✅ | 1 | 1 | `1`=공고게시일시(pblancDate) / `2`=개찰일시 |
| `type` | 응답 타입 | ❌ | 4 | `json` | 생략 시 XML, `json` 명시 시 JSON |
| `inqryBgnDt` | 조회시작일시 | 조건부 | 12 | `202507010000` | `YYYYMMDDHHMM`. `inqryDiv=1`/`2` 모두 사실상 필수 |
| `inqryEndDt` | 조회종료일시 | 조건부 | 12 | `202507012359` | `YYYYMMDDHHMM`. 동상 |
| `bidNtceNm` | 입찰공고명 | ❌ | 1000 | `모션캡쳐시스템 업그레이드` | 부분 일치 가능 |
| `ntceInsttCd` | 공고기관코드 | ❌ | 7 | `Z001351` | 행자부코드 우선, 없으면 조달청 부여 코드 |
| `ntceInsttNm` | 공고기관명 | ❌ | 400 | `재단법인부산테크노파크` | 부분 일치 가능 |
| `dminsttCd` | 수요기관코드 | ❌ | 7 | `Z001351` | **한국환경공단 필터링 시 핵심** |
| `dminsttNm` | 수요기관명 | ❌ | 400 | | 부분 일치 가능 |
| `refNo` | 참조번호 | ❌ | 105 | `물품25-49` | |
| `prtcptLmtRgnCd` | 참가제한지역코드 | ❌ | 2 | `00` | 아래 코드표 참조 |
| `prtcptLmtRgnNm` | 참가제한지역명 | ❌ | 100 | `전국` | |
| `indstrytyCd` | 업종코드 | ❌ | 4 | `0003` | |
| `indstrytyNm` | 업종명 | ❌ | 100 | `토목공사업` | 부분 일치 가능 |
| `presmptPrceBgn` | 추정가격시작 | ❌ | 25 | `81818100` | (원화) 이상 |
| `presmptPrceEnd` | 추정가격종료 | ❌ | 25 | `81818200` | (원화) 이하 |
| `dtilPrdctClsfcNo` | 세부품명번호 | ❌ | 10 | `4921181901` | **분석 대상 품목 풀의 핵심 키** |
| `masYn` | 다수공급경쟁자여부 | ❌ | 1 | `N` | MAS(다수공급자계약) 분리 시 사용 |
| `prcrmntReqNo` | 조달요청번호 | ❌ | 13 | `R25DC00066664` | |
| `bidClseExcpYn` | 입찰마감제외여부 | ❌ | 1 | `N` | |
| `intrntnlDivCd` | 국제구분코드 | ❌ | 1 | `1` | `1`=국내 / `2`=국제 |

### 참가제한지역코드 (`prtcptLmtRgnCd`)

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

## 호출 규칙 (에이전트용)

### 시간 윈도우
- `inqryBgnDt`/`inqryEndDt`는 명세상 옵션(0)이지만 실제로는 **`inqryDiv`와 함께 항상 같이** 보내야 의미 있는 결과가 나옴
- 일시 포맷: 요청은 **`YYYYMMDDHHMM`(12자리)**, 응답은 **`YYYY-MM-DD HH:MM:SS`(19자리)** 또는 일부 16자리 (`YYYY-MM-DD HH:MM`)
- **1개월 윈도우 제약**(낙찰·예가 API와 동일하게) 적용 가능성 있음 → 안전하게 일/주 단위 호출 권장

### 분석 파이프라인 표준 호출 패턴 (한국환경공단 환경기초시설)

```python
# 1단계: 일별 + 수요기관 + 세부품명번호 필터로 공고 풀 수집
get_bid_pblanc(
    inqryDiv=1,
    inqryBgnDt=f"{yyyymmdd}0000",
    inqryEndDt=f"{yyyymmdd}2359",
    dminsttCd=ENV_CORP_CODE,            # 한국환경공단 행자부코드
    dtilPrdctClsfcNo="4921181901",      # 환경기초시설 자재 코드 (반복 호출)
    numOfRows=999,
    pageNo=1,
)
# → totalCount > numOfRows 인 경우 pageNo 증가시켜 페이징
# → 결과의 bidNtceNo가 후속 낙찰(16번)·개찰결과(9번) 호출의 입력
```

### 페이징
- `totalCount`로 전체 row 수 파악 → `ceil(totalCount / numOfRows)`만큼 `pageNo` 증가
- 같은 검색조건으로 페이징하는 동안 새 공고가 끼어들어 중복/누락 가능성 있음 → 일자 단위로 쪼개고 `bidNtceNo` 기준 dedupe 권장

## Response Parameters

응답은 `<response><header/><body><items><item/>...</items></body></response>` 구조의 XML(또는 `type=json` 시 JSON). item당 약 **70개 필드**. 카테고리별로 정리.

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

### item — 식별자/공고 메타

| name | ko | size | required | sample | note |
|---|---|---|---|---|---|
| `bidNtceNo` | 입찰공고번호 | 40 | ✅ | `R25BK00934850` | 차세대 13자리(R+년도2+단계구분2+순번8). 단계: BK=입찰/TA=계약/DD=발주계획/BD=사전규격/BK=통합입찰. **size 정의 vs 실제 불일치(40 vs 13)** |
| `bidNtceOrd` | 입찰공고차수 | 3 | ✅ | `000` | 재공고/재입찰 발생 시 증가 |
| `reNtceYn` | 재공고여부 | 1 | ❌ | `N` | Y/N |
| `rgstTyNm` | 등록유형명 | 100 | ✅ | `조달청 또는 나라장터 자체 공고건` | "조달청 또는 나라장터 자체 공고건" / "나라장터 기타 공고건" |
| `ntceKindNm` | 공고종류명 | 100 | ❌ | `등록공고` | 등록/변경/취소/재공고 |
| `intrbidYn` | 국제입찰여부 | 1 | ❌ | `N` | WTO/FTA 적용 여부 |
| `bidNtceDt` | 입찰공고일시 | 19 | ❌ | `2025-07-01 07:54:07` | |
| `refNo` | 참조번호 | 105 | ❌ | `물품25-49` | 자체전자조달시스템의 공고번호 |
| `bidNtceNm` | 입찰공고명 | 1000 | ✅ | `모션캡쳐시스템 업그레이드` | |
| `untyNtceNo` | 통합공고번호 | 40 | ❌ | `R25BM00300438` | 통합공고(BM) 그룹핑 키 |
| `orderPlanUntyNo` | 발주계획통합번호 | 35 | ❌ | `R25DD20290101` | 발주계획(DD) 연계 키 |
| `bfSpecRgstNo` | 사전규격등록번호 | 17 | ❌ | `R25BD00078286` | 사전규격(BD) 연계 키 |
| `chgDt` | 변경일시 | 19 | ❌ | | |
| `chgNtceRsn` | 변경공고사유 | 4000 | ❌ | `입찰기간 부족` | 변경/취소 시 사유 |
| `rgstDt` | 등록일시 | 19 | ✅ | `2025-07-01 07:54:07` | |

### item — 기관 정보

| name | ko | size | required | sample | note |
|---|---|---|---|---|---|
| `ntceInsttCd` | 공고기관코드 | 7 | ❌ | `Z001351` | 행자부코드 우선 |
| `ntceInsttNm` | 공고기관명 | 400 | ❌ | `재단법인부산테크노파크` | |
| `dminsttCd` | 수요기관코드 | 7 | ✅ | `Z001351` | **한국환경공단 필터의 핵심** |
| `dminsttNm` | 수요기관명 | 400 | ✅ | `재단법인부산테크노파크` | 공고기관과 동일할 수 있음 |
| `ntceInsttOfclNm` | 공고기관담당자명 | 35 | ❌ | `주혜련` | |
| `ntceInsttOfclTelNo` | 공고기관담당자전화번호 | 25 | ❌ | `051-974-9019` | |
| `ntceInsttOfclEmailAdrs` | 공고기관담당자이메일주소 | 100 | ❌ | `ksinichi@btp.or.kr` | |
| `dminsttOfclEmailAdrs` | 수요기관담당자이메일주소 | 100 | ❌ | | |
| `exctvNm` | 집행관명 | 35 | ❌ | `주혜련` | |

### item — 입찰 라이프사이클 일정

| name | ko | size | required | sample | note |
|---|---|---|---|---|---|
| `bidQlfctRgstDt` | 입찰참가자격등록마감일시 | 19 | ❌ | `2025-07-13 18:00` | **16자리(`YYYY-MM-DD HH:MM`) 케이스** |
| `cmmnSpldmdAgrmntRcptdocMethd` | 공동수급협정서접수방식 | 500 | ❌ | `없음` | "전자"/"수기"/"없음"/"공고서참고" |
| `cmmnSpldmdAgrmntClseDt` | 공동수급협정마감일시 | 19 | ❌ | `2025-07-13 18:00` | 동상 16자리 |
| `cmmnSpldmdCorpRgnLmtYn` | 공동수급업체지역제한여부 | 1 | ❌ | `N` | |
| `bidBeginDt` | 입찰개시일시 | 19 | ❌ | `2025-07-01 10:00:00` | |
| `bidClseDt` | 입찰마감일시 | 19 | ❌ | `2025-07-14 10:00:00` | |
| `opengDt` | 개찰일시 | 19 | ❌ | `2025-07-14 11:00:00` | 집행관이 개찰 가능한 시작일시 (실개찰 ≠) |
| `rbidOpengDt` | 재입찰개찰일시 | 19 | ❌ | `2025-07-14 11:00:00` | 재입찰 케이스 |
| `bidWgrnteeRcptClseDt` | 입찰보증서접수마감일시 | 19 | ❌ | | |
| `arsltApplDocRcptDt` | 실적신청서접수일시 | 19 | ❌ | `2025-07-13 18:00` | |
| `arsltApplDocRcptMthdNm` | 실적신청서접수방법명 | 50 | ❌ | `전자문서` | |

### item — 가격/예산

| name | ko | size | required | sample | note |
|---|---|---|---|---|---|
| `asignBdgtAmt` | 배정예산금액 | 25 | ❌ | `90000000` | (원화) 사업목적 달성을 위해 배정된 예산 |
| `presmptPrce` | 추정가격 | 25 | ❌ | `81818182` | (원화) 부가세·조달수수료 제외 |
| `prdctUprc` | 물품단가 | 25 | ❌ | `90000000` | |
| `VAT` | 부가가치세 | 25 | ❌ | `8181818` | |
| `indutyVAT` | 주공종부가가치세 | 25 | ❌ | | |
| `bidPrtcptFee` | 입찰참가수수료 | 21 | ❌ | `0` | |
| `bidPrtcptFeePaymntYn` | 입찰참가수수료납부여부 | 30 | ❌ | | "전자납부"/"수기 및 전자납부"/"수기"/"없음" |
| `bidGrntymnyPaymntYn` | 입찰보증금납부여부 | 30 | ❌ | | "전자납부허용"/"불허" |
| `crdtrNm` | 채권자명 | 200 | ❌ | `원장` | 입찰보증금 보증채권자명 |
| `sucsfbidLwltRate` | 낙찰하한율 | 22 | ❌ | `87.745` | 개찰 시 사용하는 % |

### item — 품목 정보

| name | ko | size | required | sample | note |
|---|---|---|---|---|---|
| `dtilPrdctClsfcNo` | 세부품명번호 | 10 | ❌ | `4921181901` | **분석 대상 품목 키**. 8자리 분류 + 2자리 식별번호 |
| `dtilPrdctClsfcNoNm` | 세부품명 | 200 | ❌ | `동작분석기` | 한글명 |
| `prdctSpecNm` | 물품규격명 | 200 | ❌ | `규격서에 따름` | |
| `prdctQty` | 물품수량 | 25 | ❌ | `1` | |
| `prdctUnit` | 물품단위 | 30 | ❌ | `SET` | |
| `dlvrTmlmtDt` | 납품기한일시 | 19 | ❌ | `2025-12-30 00:00` | |
| `dlvrDaynum` | 납품일수 | 5 | ❌ | `90` | |
| `dlvryCndtnNm` | 인도조건명 | 200 | ❌ | `납품장소차상도` | |
| `purchsObjPrdctList` | 구매대상물품목록 | 4000 | 0..n | `[1^4921181901^동작분석기]` | **다건일 수 있음**. 포맷 `[순번^세부품명번호^세부품명]`, 콤마 구분 |

### item — 입찰조건/자격제한

| name | ko | size | required | sample | note |
|---|---|---|---|---|---|
| `bidMethdNm` | 입찰방식명 | 500 | ❌ | `전자입찰` | |
| `cntrctCnclsMthdNm` | 계약체결방법명 | 500 | ✅ | `제한경쟁` | 일반경쟁/제한경쟁/지명경쟁/수의계약 |
| `rbidPermsnYn` | 재입찰허용여부 | 1 | ❌ | `Y` | 유찰 시 재공고 없이 다시 입찰 |
| `prdctClsfcLmtYn` | 물품분류제한여부 | 1 | ❌ | `Y` | 물품분류번호로 제한 시 Y |
| `mnfctYn` | 제조여부 | 1 | ❌ | `N` | Y면 제조물품으로 등록되어 있어야 투찰 가능 |
| `prearngPrceDcsnMthdNm` | 예정가격결정방법명 | 20 | ❌ | `복수예가` | "복수예가" / "단일예정가격" |
| `totPrdprcNum` | 총예가건수 | 20 | ❌ | `15` | 보통 15 (복수예가 풀 사이즈) |
| `drwtPrdprcNum` | 추첨예가건수 | 20 | ❌ | `4` | 추첨될 예가 개수 |
| `dsgntCmptYn` | 지명경쟁여부 | 1 | ❌ | `N` | |
| `brffcBidprcPermsnYn` | 지사투찰허용여부 | 1 | ❌ | | 지역제한 공고에 한해 |
| `indstrytyLmtYn` | 업종제한여부 | 1 | ❌ | `Y` | |
| `rgnLmtBidLocplcJdgmBssCd` | 지역제한입찰소재지판단기준코드 | 1 | ❌ | `N` | |
| `rgnLmtBidLocplcJdgmBssNm` | 지역제한입찰소재지판단기준명 | 25 | ❌ | `본사또는참여지사소재지` | |
| `rsrvtnPrceReMkngMthdNm` | 예비가격재작성방법명 | 50 | ❌ | `재입찰시 예비가격을 다시 생성하여 예정가격이 산정됩니다.` | |
| `infoBizYn` | 정보화사업여부 | 1 | ❌ | `N` | Y/N |

### item — 낙찰방법/평가

| name | ko | size | required | sample | note |
|---|---|---|---|---|---|
| `sucsfbidMthdCd` | 낙찰방법코드 | 9 | ❌ | `낙030002` | 한글 1자리 + 숫자 6자리 |
| `sucsfbidMthdNm` | 낙찰방법명 | 700 | ❌ | `제안적격자 중 예가 내 최저가 투찰자` | |
| `sucsfbidMthdAppStd` | 낙찰방법적용기준 | 500 | ❌ | `조달청 시설공사 적격심사세부기준` | |
| `techAbltEvlRt` | 기술능력평가비율 | 25 | ❌ | `80` | 협상에 의한 낙찰 시 (%) |
| `bidPrceEvlRt` | 입찰가격평가비율 | 25 | ❌ | `20` | 협상에 의한 낙찰 시 (%) |

### item — 공동수급

| name | ko | size | required | sample | note |
|---|---|---|---|---|---|
| `cmmnSpldmdMethdCd` | 공동수급방식코드 | 15 | ❌ | `공500012` | 공500001~공500012 |
| `cmmnSpldmdMethdNm` | 공동수급방식명 | 500 | ❌ | `(없음)공동수급불허` | 공동이행/분담이행/주계약자관리방식 등 |

### item — 공고규격서/URL

| name | ko | size | required | sample | note |
|---|---|---|---|---|---|
| `ntceSpecDocUrl1` ~ `ntceSpecDocUrl10` | 공고규격서URL 1~10 | 800 | ❌ | (긴 다운로드 URL) | 최대 10개 |
| `ntceSpecFileNm1` ~ `ntceSpecFileNm10` | 공고규격파일명 1~10 | 400 | ❌ | `붙임2. 입찰공고문(규가동시)_물품.hwp` | 최대 10개. **명세서 `ntceSpecFileNm3` size가 256400으로 표기되어 있으나 OCR 오류로 추정 (다른 슬롯은 모두 400)** |
| `bidNtceDtlUrl` | 입찰공고상세URL | 512 | ❌ | (g2b.go.kr 링크) | 나라장터 상세화면 |
| `bidNtceUrl` | 입찰공고URL | 500 | ❌ | (g2b.go.kr 링크) | |
| `stdNtceDocUrl` | 표준공고서URL | 800 | ❌ | (다운로드 URL) | |
| `opengPlce` | 개찰장소 | 100 | ❌ | `국가종합전자조달시스템(나라장터)` | |

> **항목구분**: ✅ 필수(1), ❌ 옵션(0). 0..n은 다건 가능.

## 파이프라인에서의 역할

이 API는 **분석 파이프라인의 seed**다. 다른 API들은 모두 여기서 나오는 키에 의존한다:

```
getBidPblancListInfoThngPPSSrch  (이 API, 14번)
   │
   ├─ bidNtceNo + bidNtceOrd ──► getOpengResultListInfoThng (개찰결과)
   │                          ──► getOpengResultListInfoThngPreparPcDetail (9번, 복수예가)
   │                          ──► getScsbidListSttusThngPPSSrch (16번, 낙찰자)
   │                                                                  │
   │                                                                  ▼
   │                                                              BRN(사업자등록번호)
   │                                                                  │
   │                                                                  ├─ getPrcrmntCorpInfo (업체 메타)
   │                                                                  ├─ 공공구매 인증서 (SR)
   │                                                                  ├─ 부정당제재 정보
   │                                                                  └─ ...
   │
   ├─ dtilPrdctClsfcNo ──► 분석 대상 품목 풀 정의
   ├─ dminsttCd        ──► 수요기관 필터 (한국환경공단)
   ├─ untyNtceNo       ──► 통합공고 그룹핑
   ├─ orderPlanUntyNo  ──► 발주계획 연계
   └─ bfSpecRgstNo     ──► 사전규격 연계
```

### 한국환경공단 환경기초시설 추출 절차

1. **`dminsttCd`**에 한국환경공단 행자부코드 지정 → 환경공단 발주 공고만 수신
2. **`dtilPrdctClsfcNo`** 화이트리스트(소각·하수처리·바이오 관련 자재 코드 사전 정의)로 반복 호출 → 환경기초시설 자재 공고로 좁힘
3. 결과의 `bidNtceNo` 풀이 후속 분석의 입력
4. `presmptPrce` 범위로 추가 필터링 (소액 공고 제외 등) 가능

## Sample Request

```
http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoThngPPSSrch
  ?type=xml
  &inqryDiv=1
  &inqryBgnDt=202507010000
  &inqryEndDt=202507012359
  &numOfRows=10
  &pageNo=1
  &bidNtceNm=모션캡쳐시스템%20업그레이드
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
        <bidNtceNo>R25BK00934850</bidNtceNo>
        <bidNtceOrd>000</bidNtceOrd>
        <reNtceYn>N</reNtceYn>
        <rgstTyNm>조달청 또는 나라장터 자체 공고건</rgstTyNm>
        <ntceKindNm>등록공고</ntceKindNm>
        <bidNtceDt>2025-07-01 07:54:07</bidNtceDt>
        <bidNtceNm>모션캡쳐시스템 업그레이드</bidNtceNm>
        <ntceInsttCd>Z001351</ntceInsttCd>
        <ntceInsttNm>재단법인부산테크노파크</ntceInsttNm>
        <dminsttCd>Z001351</dminsttCd>
        <dminsttNm>재단법인부산테크노파크</dminsttNm>
        <bidMethdNm>전자입찰</bidMethdNm>
        <cntrctCnclsMthdNm>제한경쟁</cntrctCnclsMthdNm>
        <bidBeginDt>2025-07-01 10:00:00</bidBeginDt>
        <bidClseDt>2025-07-14 10:00:00</bidClseDt>
        <opengDt>2025-07-14 11:00:00</opengDt>
        <prearngPrceDcsnMthdNm>복수예가</prearngPrceDcsnMthdNm>
        <totPrdprcNum>15</totPrdprcNum>
        <drwtPrdprcNum>4</drwtPrdprcNum>
        <asignBdgtAmt>90000000</asignBdgtAmt>
        <presmptPrce>81818182</presmptPrce>
        <dtilPrdctClsfcNo>4921181901</dtilPrdctClsfcNo>
        <dtilPrdctClsfcNoNm>동작분석기</dtilPrdctClsfcNoNm>
        <prdctQty>1</prdctQty>
        <prdctUnit>SET</prdctUnit>
        <prdctUprc>90000000</prdctUprc>
        <dlvrDaynum>90</dlvrDaynum>
        <purchsObjPrdctList>[1^4921181901^동작분석기]</purchsObjPrdctList>
        <untyNtceNo>R25BM00300438</untyNtceNo>
        <orderPlanUntyNo>R25DD20290101</orderPlanUntyNo>
        <bfSpecRgstNo>R25BD00078286</bfSpecRgstNo>
        <sucsfbidMthdCd>낙030002</sucsfbidMthdCd>
        <sucsfbidMthdNm>제안적격자 중 예가 내 최저가 투찰자</sucsfbidMthdNm>
        <ntceSpecDocUrl1>https://www.g2b.go.kr/.../downloadFile.do?...&fileSeq=1...</ntceSpecDocUrl1>
        <ntceSpecFileNm1>붙임2. 입찰공고문(규가동시)_물품.hwp</ntceSpecFileNm1>
        <!-- ... 약 70개 필드 ... -->
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
type InqryDiv = "1" | "2";
type IntrntnlDivCd = "1" | "2";

interface GetBidPblancParams {
  ServiceKey: string;
  numOfRows: number;
  pageNo: number;
  inqryDiv: InqryDiv;
  type?: "json" | "xml";
  inqryBgnDt?: string;            // YYYYMMDDHHMM
  inqryEndDt?: string;
  bidNtceNm?: string;
  ntceInsttCd?: string;
  ntceInsttNm?: string;
  dminsttCd?: string;
  dminsttNm?: string;
  refNo?: string;
  prtcptLmtRgnCd?: string;        // "00" | "11" | ... | "99"
  prtcptLmtRgnNm?: string;
  indstrytyCd?: string;
  indstrytyNm?: string;
  presmptPrceBgn?: string;        // 숫자 문자열 (원화)
  presmptPrceEnd?: string;
  dtilPrdctClsfcNo?: string;      // 10자리
  masYn?: "Y" | "N";
  prcrmntReqNo?: string;
  bidClseExcpYn?: "Y" | "N";
  intrntnlDivCd?: IntrntnlDivCd;
}

// 응답 item — 카테고리별로 분리한 인터페이스
interface BidNoticeIdentity {
  bidNtceNo: string;
  bidNtceOrd: string;
  reNtceYn: "Y" | "N" | "";
  rgstTyNm: string;
  ntceKindNm: string;
  intrbidYn: "Y" | "N" | "";
  bidNtceDt: string;
  refNo: string;
  bidNtceNm: string;
  untyNtceNo: string;
  orderPlanUntyNo: string;
  bfSpecRgstNo: string;
  chgDt: string;
  chgNtceRsn: string;
  rgstDt: string;
}

interface BidNoticeInstitution {
  ntceInsttCd: string;
  ntceInsttNm: string;
  dminsttCd: string;
  dminsttNm: string;
  ntceInsttOfclNm: string;
  ntceInsttOfclTelNo: string;
  ntceInsttOfclEmailAdrs: string;
  dminsttOfclEmailAdrs: string;
  exctvNm: string;
}

interface BidNoticeSchedule {
  bidQlfctRgstDt: string;          // 16자리 또는 19자리
  cmmnSpldmdAgrmntRcptdocMethd: string;
  cmmnSpldmdAgrmntClseDt: string;
  cmmnSpldmdCorpRgnLmtYn: "Y" | "N" | "";
  bidBeginDt: string;
  bidClseDt: string;
  opengDt: string;
  rbidOpengDt: string;
  bidWgrnteeRcptClseDt: string;
  arsltApplDocRcptDt: string;
  arsltApplDocRcptMthdNm: string;
}

interface BidNoticePrice {
  asignBdgtAmt: string;             // 숫자 문자열
  presmptPrce: string;
  prdctUprc: string;
  VAT: string;
  indutyVAT: string;
  bidPrtcptFee: string;
  bidPrtcptFeePaymntYn: string;
  bidGrntymnyPaymntYn: string;
  crdtrNm: string;
  sucsfbidLwltRate: string;
}

interface BidNoticeItem {
  dtilPrdctClsfcNo: string;          // 10자리
  dtilPrdctClsfcNoNm: string;
  prdctSpecNm: string;
  prdctQty: string;
  prdctUnit: string;
  dlvrTmlmtDt: string;
  dlvrDaynum: string;
  dlvryCndtnNm: string;
  /** "[순번^세부품명번호^세부품명]" 콤마 구분, 다건 가능 */
  purchsObjPrdctList: string;
}

interface BidNoticeCondition {
  bidMethdNm: string;
  cntrctCnclsMthdNm: string;
  rbidPermsnYn: "Y" | "N" | "";
  prdctClsfcLmtYn: "Y" | "N" | "";
  mnfctYn: "Y" | "N" | "";
  prearngPrceDcsnMthdNm: string;     // "복수예가" / "단일예정가격"
  totPrdprcNum: string;
  drwtPrdprcNum: string;
  dsgntCmptYn: "Y" | "N" | "";
  brffcBidprcPermsnYn: "Y" | "N" | "";
  indstrytyLmtYn: "Y" | "N" | "";
  rgnLmtBidLocplcJdgmBssCd: string;
  rgnLmtBidLocplcJdgmBssNm: string;
  rsrvtnPrceReMkngMthdNm: string;
  infoBizYn: "Y" | "N" | "";
}

interface BidNoticeAward {
  sucsfbidMthdCd: string;
  sucsfbidMthdNm: string;
  sucsfbidMthdAppStd: string;
  techAbltEvlRt: string;
  bidPrceEvlRt: string;
}

interface BidNoticeJointSupply {
  cmmnSpldmdMethdCd: string;
  cmmnSpldmdMethdNm: string;
}

interface BidNoticeSpecDocs {
  ntceSpecDocUrl1: string;  ntceSpecFileNm1: string;
  ntceSpecDocUrl2: string;  ntceSpecFileNm2: string;
  ntceSpecDocUrl3: string;  ntceSpecFileNm3: string;
  ntceSpecDocUrl4: string;  ntceSpecFileNm4: string;
  ntceSpecDocUrl5: string;  ntceSpecFileNm5: string;
  ntceSpecDocUrl6: string;  ntceSpecFileNm6: string;
  ntceSpecDocUrl7: string;  ntceSpecFileNm7: string;
  ntceSpecDocUrl8: string;  ntceSpecFileNm8: string;
  ntceSpecDocUrl9: string;  ntceSpecFileNm9: string;
  ntceSpecDocUrl10: string; ntceSpecFileNm10: string;
  bidNtceDtlUrl: string;
  bidNtceUrl: string;
  stdNtceDocUrl: string;
  opengPlce: string;
}

type BidNoticeRow = BidNoticeIdentity
  & BidNoticeInstitution
  & BidNoticeSchedule
  & BidNoticePrice
  & BidNoticeItem
  & BidNoticeCondition
  & BidNoticeAward
  & BidNoticeJointSupply
  & BidNoticeSpecDocs;

// 도메인 변환
interface BidNoticeNormalized {
  bidNtceNo: string;
  bidNtceOrd: string;
  bidNtceNm: string;
  dminsttCd: string;
  dminsttNm: string;
  presmptPrce: number;
  asignBdgtAmt: number;
  bidNtceDt: Date;
  opengDt: Date | null;
  bidClseDt: Date | null;
  /** 1건의 공고에 여러 품목이 묶일 수 있음 */
  items: Array<{ seq: number; dtilPrdctClsfcNo: string; nm: string }>;
  specDocs: Array<{ url: string; filename: string }>;
}
```

### 변환 시 주의

- **금액 필드 모두 문자열**: `presmptPrce`, `asignBdgtAmt`, `prdctUprc`, `VAT` 등 → `Number()` 변환. 21~25자리 허용이라 큰 금액은 BigInt 고려.
- **`purchsObjPrdctList` 파싱**: `[순번^세부품명번호^세부품명]` 패턴이 다건이면 `,`로 구분. 1건 공고에 여러 세부품명번호가 묶일 수 있으므로 분석 단위가 (공고, 품목)일 때 explode 필요.
- **시간 포맷 혼재**: 19자리(`YYYY-MM-DD HH:MM:SS`)와 16자리(`YYYY-MM-DD HH:MM`) 혼재. `bidQlfctRgstDt`, `cmmnSpldmdAgrmntClseDt` 등이 16자리. 파서는 둘 다 허용해야 함.
- **빈 문자열 vs null**: 거의 모든 옵션 필드가 미입력 시 빈 문자열 `""`로 옴. 정규화 단계에서 `null` 또는 적절한 기본값으로 통일.
- **Y/N 필드**: `""` (미지정), `Y`, `N` 3-state. 단순 boolean으로 캐스팅하기 전에 미지정 처리 결정 필요.
- **`ntceSpecDocUrl*`/`ntceSpecFileNm*`**: 10개 슬롯 중 빈 슬롯이 다수. URL/파일명 쌍을 묶어서 비어있는 쌍은 제거 후 배열로 정규화 권장.

## Error Codes

`_common.md`의 공통 에러코드 표 참조 (`00`/`30`/`99` + 게이트웨이 `OpenAPI_ServiceResponse`).

## 미해결 / 확인 필요

- [ ] `bidNtceNo` size 정의(40) vs 실제 데이터(13자리) 불일치 — 자체 가이드 확정 필요
- [ ] `ntceSpecFileNm3` size `256400` 표기 — OCR 오류로 추정, 다른 슬롯과 동일하게 400으로 가정
- [ ] `inqryDiv=1`/`2` 사용 시 최대 조회 기간 제한 명세에 없음 — 1개월 단위 안전 호출 권장
- [ ] `prtcptLmtRgnCd`로 다중 지역 지정 가능 여부 (콤마 구분?) 확인 필요
- [ ] `dtilPrdctClsfcNo` 다중값 입력 가능 여부 확인 필요 (가능하면 호출 횟수 대폭 절감)
- [ ] `numOfRows` 최대값 (보통 999 추정)

## 참고

- **연계 API**:
  - 9번 `getOpengResultListInfoThngPreparPcDetail` — 본 공고의 복수예가 풀
  - 16번 `getScsbidListSttusThngPPSSrch` — 본 공고의 최종 낙찰자
  - 사용자정보 `getPrcrmntCorpInfo` — 낙찰자 BRN으로 업체 메타 조회
- **연계 키**:
  - `bidNtceNo + bidNtceOrd`: 본 공고를 후속 API와 join
  - `untyNtceNo`: 통합공고(BM) 단위로 같은 사업의 여러 공고 묶기
  - `orderPlanUntyNo`: 발주계획(DD)으로 거슬러 올라가 사업 전체 추적
  - `bfSpecRgstNo`: 사전규격(BD) — 공고 이전의 규격 협의 단계 추적
