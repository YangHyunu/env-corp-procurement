---
title: 조달업체 등록 내역 (CSV)
source: https://www.data.go.kr/data/15053474/fileData.do
report_id: UI-ADOAAA-008R
provider: 조달청 (조달데이터관리팀)
type: csv-bulk
role: brn-master
applies_to:
  - mart_company_master
  - mart_company_sr (1차 후보)
status: documented
last_verified: 2026-04-25
---

# 조달업체 등록 내역 (CSV 데이터셋)

조달청 나라장터에 등록된 **전체 조달업체 64만여 곳**의 메타·SR 1차 분류 자료. 분석 파이프라인의 **BRN 마스터 출처** 및 **SR 인증 1차 후보 풀** 역할.

OpenAPI 형태가 아닌 **CSV 일괄 다운로드** 방식. 처리 라이프사이클이 G2B API와 다르므로 별도 문서로 관리.

## 메타

| 항목 | 값 |
|---|---|
| 출처 | data.go.kr — 조달업체 등록 내역 (`fileData/15053474`) |
| 보고서 ID | UI-ADOAAA-008R |
| 제공 | 조달청 조달데이터관리팀 |
| 라이선스 | 이용허락범위 제한 없음 |
| 갱신 주기 | 수시 (자동 갱신) — 보수적으로 **주 1회** 가정 |
| 추출 기준 | 전일(D-1)까지의 데이터 (당일 변경분 미반영) |
| 제외 대상 | 이중등록·등록취소·폐업 업체 |

## 파일 형식 ⚠️

공공데이터포털 CSV의 흔한 함정 — UTF-8 아님:

| 항목 | 값 |
|---|---|
| 인코딩 | **UTF-16** |
| 구분자 | **탭(`\t`)** |
| 행 수 (실측) | **647,184** |
| 컬럼 수 | 14 |
| 메모리 (pandas) | 약 70 MB |

```python
df = pd.read_csv(path, encoding="utf-16", sep="\t",
                 dtype={"사업자등록번호": str})
```

## 스키마 (14 컬럼)

| 컬럼 | 타입 | non-null | 의미 / 비고 |
|---|---|---|---|
| `업체명` | str | 100% | |
| `사업자등록번호` | str | 100% | 10자리 숫자(99.9%) 또는 `F`+9자리 (국외, 0.1%) |
| `업체소재시군구` | str | 100% | `충청남도 천안시 동남구` 등 / 국외는 `국외소재 기타지역` |
| `본사지사구분` | str | 100% | `본사`(98.4%) / `지사`(1.6%) |
| `업체국가` | str | 100% | `대한민국`(99.9%) 외 26+개국 |
| `기업구분` | str | 99.99% | `중소기업`(96.7%) / `비영리법인등기타` / `중견기업` / `대기업` |
| `대표업종` | str | 60.5% | 자유 텍스트 (예: `건설기계대여업`, `연명신고사업자`) |
| `제조업체여부` | str | 100% | `Y`(10.6%) / `N`(89.4%) |
| `대표세부품명번호` | float→int | 61.1% | 10자리 정수. **float로 로드되므로 변환 필수** |
| `대표세부품명` | str | 61.1% | 10자리 코드의 한글명 |
| `나라장터등록일자` | int | 100% | `YYYYMMDD` 8자리 정수 |
| `여성기업인증여부` | str | 67.0% | ⚠️ **인증서 아닌 자동 판별** — 아래 별도 섹션 |
| `장애인기업인증여부` | str | 59.0% | `Y`/`N` (실제 인증 신청·심사 기반) |
| `사회적기업인증여부` | str | 58.5% | `Y`/`N` (실제 인증 신청·심사 기반) |

## ⚠️ 컬럼 의미 주의 — 가장 큰 함정

### `여성기업인증여부`는 **인증서 보유가 아니라 자동 판별**

| 항목 | 의미 |
|---|---|
| `Y` | 대표자 주민등록번호 기반 성별 = **여성** |
| `N` | 대표자가 남성 또는 법인격으로 주민번호 부재 |
| 결측 | 주민번호 자체 미보유 (외국기업, 특수 법인격) |

❌ 「여성기업지원에 관한 법률」 상의 **여성기업확인서**(여성기업종합지원센터 발급) 보유 여부가 **아님**. 진짜 여성기업확인서엔:
- 발급일·만료일 (재인증 필요)
- 자격 심사 (대표 + 실질 경영 모두 여성)
- 조달 가점·우대 자격

이 CSV의 `Y`는 단순히 "대표=여성"이라는 사실만 알려줌. 분석 시 이 차이 인지 필수.

### `장애인기업` / `사회적기업`은 진짜 인증 기반

| 항목 | 의미 |
|---|---|
| `Y` | 해당 인증 보유 |
| `N` | 미보유 |
| 결측 | 미신청 (또는 데이터 누락) |

다만 **만료일이 이 CSV에 없음** → 인증 유효성 검증은 외부 SR API(KEAD, 사회적기업 인증포털 등)로 보강.

### SR 3컬럼 결측 동시성

실측: 3컬럼 모두 결측인 행이 정확히 **204,949건 (31.7%)**, 모두 입력인 행 **58.0%**, 부분 결측 10.3%. 즉 대부분 **3개가 함께 입력 또는 함께 결측**. 데이터 입력 시점에 일괄 처리됨을 시사.

## 데이터 특성 요약 (실측 2026-04-25)

### 사업자등록번호 패턴

| 패턴 | 카운트 | 비율 |
|---|---|---|
| 숫자 10자리 | 646,404 | 99.88% |
| `F`+9자리 (국외) | 778 | 0.12% |
| 숫자 9자리 (이상치) | 2 | 0.0003% |

F-prefix 검증:
- F-prefix 778개 중 **750개가 국외 업체** (96.4% 일치)
- 이상치: F-prefix지만 대한민국(28건, 외국계 한국법인 추정) / 국외인데 숫자(2건, 한국 법인등록 외국기업)

### 모집단 분포

| 항목 | 값 |
|---|---|
| 중소기업 | 96.7% |
| 비영리법인 등 기타 | 2.4% |
| 중견기업 | 0.7% |
| 대기업 | 0.2% |
| 제조업체 | 10.6% |
| 국내 (대한민국) | 99.9% |

### BRN 중복 — 본사·지사 구조

- unique BRN: 644,226 (전체의 99.5%)
- 중복: 2,958건 — 같은 BRN에 본사 1개 + 지사 N개
- 극단 케이스: "프리젠"(`3501102888`) 222행

→ **PK는 `(사업자등록번호, 본사지사구분, 업체소재시군구)`** 조합이 안전.

### 품명번호

전부 **10자리 정수**, 패딩 불필요 (`min=1,010,150,201`, `max=9,999,997,001`). 다만 pandas는 `float64`로 로드하므로 int 변환 필수.

## 정규화 정책 (확정)

| 항목 | 결정 |
|---|---|
| **SR 결측 처리** | 결측 → `N` 가정. 단 `sr_data_present` 플래그 별도 컬럼 보존 |
| **F-prefix BRN** | 그대로 통과 (10자리 검증만) |
| **품명번호** | float → int → `f"{x:010d}"` |
| **본사/지사** | 분석 시 본사만 필터 (`본사지사구분 == '본사'`) 또는 (BRN, 본사지사) 복합키 |
| **제조업체** | 환경기초시설 자재 분석 시 `Y`만 필터 검토 |
| **국외 업체** | 한국환경공단 발주 분석엔 무관 → 제외 |
| **여성기업** | "자동 판별" 의미 유지. 진짜 인증서는 외부 API로 별도 |

## Python 로딩·정규화 모듈

`procurement_corp.py` 단일 파일.

```python
"""procurement_corp.py — 조달업체 등록 내역 CSV 처리."""
from __future__ import annotations

import re
import logging
from datetime import date
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


# ── 컬럼 매핑 (한글 → snake_case) ─────────────────────────
COL_RENAME = {
    "업체명":          "corp_name",
    "사업자등록번호":   "brn",
    "업체소재시군구":   "addr_sigungu",
    "본사지사구분":     "branch_type",
    "업체국가":         "country",
    "기업구분":         "corp_size",
    "대표업종":         "main_industry",
    "제조업체여부":     "is_manufacturer",
    "대표세부품명번호": "main_dtil_prdct_cd",
    "대표세부품명":     "main_dtil_prdct_nm",
    "나라장터등록일자": "g2b_registered_at",
    "여성기업인증여부": "female_ceo_flag",     # 인증서 아님!
    "장애인기업인증여부": "disabled_corp_flag",
    "사회적기업인증여부": "social_corp_flag",
}

SR_COLS = ["female_ceo_flag", "disabled_corp_flag", "social_corp_flag"]


def load(path: str | Path) -> pd.DataFrame:
    """원본 CSV 로드 (UTF-16 + 탭)."""
    df = pd.read_csv(
        path,
        encoding="utf-16",
        sep="\t",
        dtype={"사업자등록번호": str},
    )
    return df.rename(columns=COL_RENAME)


def normalize_brn(s: str | None) -> str | None:
    """국내 10자리 숫자 또는 F-prefix 10자리. 그 외 None."""
    if not s or pd.isna(s):
        return None
    s = str(s).strip()
    if s.startswith("F") and len(s) == 10:
        return s
    digits = re.sub(r"\D", "", s)
    return digits if len(digits) == 10 else None


def normalize_corp_name(s: str | None) -> str | None:
    """업체명 정규화: (주)/주식회사 등 통일."""
    if not s or pd.isna(s):
        return None
    s = str(s).strip()
    s = re.sub(r"\(주\)|주식회사", "", s)
    s = re.sub(r"\(유\)|유한회사", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """raw → 정규화 dataframe."""
    out = df.copy()

    # BRN 정규화
    out["brn"] = out["brn"].map(normalize_brn)

    # 업체명 정규화 (검색용 보조 컬럼)
    out["corp_name_normalized"] = out["corp_name"].map(normalize_corp_name)

    # 품명번호 float → 10자리 문자열
    def _pad_prdct(x):
        if pd.isna(x):
            return None
        return f"{int(x):010d}"
    out["main_dtil_prdct_cd"] = out["main_dtil_prdct_cd"].map(_pad_prdct)

    # 등록일자 int → date
    def _to_date(x):
        if pd.isna(x):
            return None
        s = str(int(x))
        if len(s) != 8:
            return None
        try:
            return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        except ValueError:
            return None
    out["g2b_registered_at"] = out["g2b_registered_at"].map(_to_date)

    # SR 데이터 존재 플래그 (3개 모두 결측이면 False)
    out["sr_data_present"] = out[SR_COLS].notna().any(axis=1)

    # SR 정규화: 결측 → N
    for col in SR_COLS:
        out[col] = out[col].fillna("N").map({"Y": True, "N": False}).astype(bool)

    # 부울 정규화
    out["is_manufacturer"] = out["is_manufacturer"].map({"Y": True, "N": False}).astype(bool)
    out["is_headquarter"] = out["branch_type"] == "본사"
    out["is_domestic"] = out["country"] == "대한민국"

    # 유효 BRN만 보존 (이상치 2건 제거)
    out = out[out["brn"].notna()].copy()

    return out


def filter_for_analysis(
    df: pd.DataFrame,
    *,
    domestic_only: bool = True,
    headquarter_only: bool = True,
    manufacturer_only: bool = False,
) -> pd.DataFrame:
    """분석 모집단 필터링."""
    mask = pd.Series(True, index=df.index)
    if domestic_only:
        mask &= df["is_domestic"]
    if headquarter_only:
        mask &= df["is_headquarter"]
    if manufacturer_only:
        mask &= df["is_manufacturer"]
    return df[mask].copy()
```

## PostgreSQL 적재 DDL

```sql
-- raw 레이어 (CSV 원본 + 수집시각)
CREATE TABLE raw_procurement_corp (
    fetched_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    file_name         TEXT NOT NULL,
    row_data          JSONB NOT NULL,
    PRIMARY KEY (fetched_at, file_name, (row_data->>'사업자등록번호'),
                 (row_data->>'본사지사구분'), (row_data->>'업체소재시군구'))
);

-- stg 레이어 (정규화)
CREATE TABLE stg_procurement_corp (
    fetched_at            TIMESTAMPTZ NOT NULL,
    brn                   VARCHAR(10) NOT NULL,
    branch_type           VARCHAR(4)  NOT NULL,    -- 본사/지사
    addr_sigungu          TEXT,
    corp_name             TEXT NOT NULL,
    corp_name_normalized  TEXT,
    country               TEXT,
    is_domestic           BOOLEAN NOT NULL,
    is_headquarter        BOOLEAN NOT NULL,
    corp_size             TEXT,                    -- 중소/중견/대/비영리
    main_industry         TEXT,
    is_manufacturer       BOOLEAN NOT NULL,
    main_dtil_prdct_cd    VARCHAR(10),
    main_dtil_prdct_nm    TEXT,
    g2b_registered_at     DATE,
    -- SR 후보 (1차)
    female_ceo_flag       BOOLEAN NOT NULL,        -- 인증서 아님!
    disabled_corp_flag    BOOLEAN NOT NULL,
    social_corp_flag      BOOLEAN NOT NULL,
    sr_data_present       BOOLEAN NOT NULL,
    PRIMARY KEY (brn, branch_type, addr_sigungu)
);

CREATE INDEX idx_stg_proc_corp_brn         ON stg_procurement_corp(brn);
CREATE INDEX idx_stg_proc_corp_dtil_prdct  ON stg_procurement_corp(main_dtil_prdct_cd);
CREATE INDEX idx_stg_proc_corp_sigungu     ON stg_procurement_corp(addr_sigungu);

-- mart 레이어 (BRN 단위 1행, 본사 우선)
CREATE TABLE mart_company_master (
    brn                   VARCHAR(10) PRIMARY KEY,
    corp_name             TEXT NOT NULL,
    corp_name_normalized  TEXT,
    addr_sigungu          TEXT,                    -- 본사 주소
    region_code           VARCHAR(2),              -- prtcptLmtRgnCd 매핑
    corp_size             TEXT,
    is_manufacturer       BOOLEAN NOT NULL,
    main_dtil_prdct_cd    VARCHAR(10),
    main_dtil_prdct_nm    TEXT,
    g2b_registered_at     DATE,
    -- SR 1차 후보
    female_ceo_flag       BOOLEAN NOT NULL,
    disabled_corp_flag    BOOLEAN NOT NULL,
    social_corp_flag      BOOLEAN NOT NULL,
    sr_data_present       BOOLEAN NOT NULL,
    -- 메타
    branch_count          INTEGER NOT NULL DEFAULT 1,
    last_synced_at        TIMESTAMPTZ NOT NULL
);
```

## 분석 파이프라인에서의 위치 (갱신본)

`getPrcrmntCorpInfo` API가 없으므로 이 CSV가 BRN 마스터 1차 출처:

```
조달업체 CSV (64만 행, 주 1회 수집)
   │
   └─► mart_company_master (BRN 단위 메타 + SR 1차)
        ↑
        │ left join (brn)
        │
   1번 API getScsbidListSttusThng (낙찰자 BRN)
        ↑
        │ bidNtceNo + bidNtceOrd
        │
   14번 API (공고 풀 — 한국환경공단 dminsttCd 필터)
        │
   5번 API (개찰결과 — 유찰 식별)
        │
   9번 API (복수예가, 옵션)


   mart_company_master + 1번 낙찰 이력
        │
        ▼
   외부 SR 인증 API들 (KEAD, 사회적기업 포털 등)
        │ 인증서 유효일·만료일 보강
        ▼
   부정당제재 API
        │ 리스크 플래그
        ▼
   mart_company_sr (BRN 단위 최종 SR 매트릭스)
```

### SR 검증 단계

이 CSV의 SR Y/N은 **1차 후보**. 분석 신뢰도를 위해 다음 보강 필요:

| 컬럼 | 1차 (이 CSV) | 2차 보강 (외부) |
|---|---|---|
| `female_ceo_flag` | 대표자 성별 (자동) | **여성기업확인서** (WBIZ — 별도 신청·심사) |
| `disabled_corp_flag` | 인증 보유 Y/N | KEAD 표준사업장 + 인증 만료일 |
| `social_corp_flag` | 인증 보유 Y/N | 사회적기업 인증포털 + 만료일 |
| (없음) | — | 중소기업 확인 (smes.go.kr — 만료일 포함) |
| (없음) | — | 창업기업 확인 (KISED — 7년 이내) |
| (없음) | — | 자활용사촌·복지공장 (보훈부) |
| (없음) | — | 부정당제재 정보 (조달청) |

## Airflow DAG 권장 구조

```
ingest_procurement_corp_csv (주 1회, 일요일 03:00)
   ├─ download_file       # 공공데이터포털에서 CSV 다운로드
   ├─ validate_schema     # 14컬럼 + 행 수 sanity check
   ├─ load_raw_to_pg      # raw_procurement_corp INSERT
   ├─ normalize_to_stg    # stg_procurement_corp 재구축 (truncate + insert)
   ├─ build_mart_master   # mart_company_master 재구축
   └─ emit_dataset        # 후속 DAG 트리거 (mart_company_sr 빌드 등)
```

수동 다운로드 단계가 자동화 어려운 경우 (포털 인증 등), 다운로드는 사람이 하고 **파일이 특정 경로에 도착하면 트리거**하는 `FileSensor` 패턴도 가능.

## 갱신·신선도 정책

| 항목 | 정책 |
|---|---|
| 다운로드 빈도 | 주 1회 (일요일 새벽) |
| raw 보관 | 모든 다운로드 회차 (이력 추적) |
| stg/mart | 매 갱신마다 재구축 (truncate + insert) |
| 변경 추적 | 별도 SCD2 필요 시 `mart_company_master_history` 추가 검토 |
| 신선도 SLA | 마지막 다운로드로부터 9일 초과 시 alert |

## 알려진 함정 체크리스트

수집·정제 코드 리뷰 시:

- [ ] CSV 인코딩은 **UTF-16**, 구분자는 **탭** (UTF-8/콤마 가정 금지)
- [ ] `사업자등록번호`는 `dtype=str`로 강제 (앞 0 손실 방지)
- [ ] `대표세부품명번호`는 float → int → 10자리 zero-pad
- [ ] `여성기업인증여부=Y`는 **인증서 보유 아닌 자동 판별** (실제 가점 자격은 외부 API로 별도 검증)
- [ ] SR 3컬럼 결측은 `N`으로 정규화하되 `sr_data_present` 플래그로 원본 결측 정보 보존
- [ ] BRN 중복 (본사+지사)은 PK에 본사지사구분·시군구 포함
- [ ] mart 단계에서 본사 1행만 살리려면 `branch_type=='본사'` 필터
- [ ] 국외 업체(F-prefix)는 한국 발주 분석엔 무관 → `is_domestic` 필터
- [ ] `나라장터등록일자`는 8자리 정수 → `date` 변환 (포맷 오류 방어)

## 미해결 / 향후 검증 필요

- [ ] 정확한 갱신 주기 — 일/주/월? 데이터 변경 빈도로 역추정 필요
- [ ] CSV 다운로드 자동화 가능성 (data.go.kr API 또는 정적 URL)
- [ ] `대표업종` 자유 텍스트의 표준화 (KSIC 매핑 가능 여부)
- [ ] 인증 만료일 정보가 정말 없는지 (별도 보고서 ID로 제공되는지)
- [ ] `기업구분 = 비영리법인등기타` 15,249건의 실제 분류 (학교법인·재단·협동조합 등)
- [ ] 같은 BRN의 본사·지사가 SR 값이 다른 케이스 존재 여부

## 참고

- **공식 페이지**: https://www.data.go.kr/data/15053474/fileData.do
- **연계 데이터셋**:
  - 1번 API `getScsbidListSttusThng` — 낙찰 BRN 출처
  - 외부 SR API 7종 — 인증 만료일·유효성 보강
  - 부정당제재 정보 — 리스크 플래그
- **연계 키**: `브랜()` → 모든 데이터셋의 통합 조인 키
