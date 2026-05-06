# ECO 추천 시스템 — 팀원 온보딩

> 환경공단 발주 담당 공무원이 **공고 발주 전** 품목·정책·예산 입력 → 후보 BRN top-K 추천하는 의사결정 지원 도구.

---

## 0. 빠른 시작 (10분)

```bash
# 1. 코드
git clone <REPO_URL> eco && cd eco

# 2. Python 환경 (uv)
curl -LsSf https://astral.sh/uv/install.sh | sh   # uv 미설치 시
uv sync                                            # .venv 자동 생성

# 3. PostgreSQL 복원
#    별도 공유받은 dump 파일을 프로젝트 내 data/dumps/ 에 두기
mkdir -p data/dumps
mv ~/Downloads/eco_2026_05_06.dump data/dumps/   # 다운로드 위치에 따라 조정
createdb eco
pg_restore --no-owner -d eco data/dumps/eco_2026_05_06.dump

# 4. 환경변수
cp .env.example .env
# .env 편집: G2B_SERVICE_KEY=<공공데이터포털 발급키>

# 5. 동작 확인
uv run python -c "from pipeline.recommend_v2 import recommend, RecommendV2Request; \
  print(recommend(RecommendV2Request(item_keyword='하수처리용 펌프', \
        budget_million_won=800, sr_filter={'social_corp':False,'female_ceo':False,'disabled_corp':False}, top_k=3)))"

# 6. 백엔드 + 프론트
uv run uvicorn api.main:app --reload --port 8000   # 터미널 1
cd frontend && npm install && npm run dev          # 터미널 2 (5173)
```

---

## 1. 전체 아키텍처

```
[조달청 G2B OpenAPI 4종]              [조달업체 CSV]
        │                                    │
        ▼ ingest                              ▼
[raw_g2b_*]  bronze                   [mart_company_master/sr]
        │                                    │
        ▼ build_stg                          │
[stg_*]  silver  (정제·정규화)        [mart_item_supply]
        │                                    │
        └────────┬───────────────────────────┘
                 ▼ build_features
        [mart_features_at_bid]  gold  (LGBM 학습용 PIT 피처)
                 │
                 ▼ pipeline.recommend_v2.recommend()
        [Stage 1 Retrieve] → [Stage 2 Rank] → [Enrich]
                 │                                
                 ▼ /api/v2/recommend
        [React 대시보드]
```

---

## 2. 데이터 모델 — 계층

### Bronze (raw) — G2B API 원본 그대로
| 테이블 | 출처 | PK |
|---|---|---|
| `raw_g2b_bid_notice` | 14번 입찰공고 | (fetched_at, bid_ntce_no, bid_ntce_ord) |
| `raw_g2b_award` | 1번 낙찰자 | (bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no) |
| `raw_g2b_opening` | 5번 개찰결과 | 동일 |
| `raw_g2b_prepar` | 9번 복수예가 | (bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no, sno) |

### Silver (stg) — 정제·정규화
| 테이블 | 핵심 컬럼 |
|---|---|
| `stg_bid_notice` | bid_ntce_no, dminstt_cd, **agency_tier** (env_corp/env_domain/other), dtil_prdct_clsfc_no, bid_ntce_dt |
| `stg_award` | bidwinnr_brn (낙찰자 BRN), sucsfbid_amt (낙찰액), sucsfbid_rate (낙찰률) |
| `stg_opening_result` | winner_brn (1순위), prtcpt_cnum |
| `stg_prepar_price` | 9번 정제 |

### Gold (mart) — 집계·조인 완료
| 테이블 | PK | 용도 |
|---|---|---|
| `mart_company_master` | brn | 업체 마스터 (이름/규모/권역/G2B 등록일) |
| `mart_company_sr` | brn | SR 인증 (여성/장애인/사회적/sr_count) |
| `mart_item_supply` | (dtil_prdct_clsfc_no, brn) | BRN×품목 공급 매트릭스 |
| `mart_bid_prepar` | (bid_ntce_no, bid_ntce_ord) | 9번 통계 집계 (15행→1행) |
| `mart_features_at_bid` | (bid_ntce_no, bid_ntce_ord, brn) | **LGBM 학습용 30 PIT 피처** |

---

## 3. ER 관계 (간략)

```mermaid
erDiagram
    stg_bid_notice ||--o{ stg_award : "공고당 낙찰자"
    stg_bid_notice ||--o{ stg_opening_result : "공고당 개찰"
    stg_bid_notice ||--o{ mart_bid_prepar : "공고당 9번 통계"
    mart_company_master ||--|| mart_company_sr : "BRN 1:1"
    mart_company_master ||--o{ mart_item_supply : "BRN의 품목 공급"
    mart_company_master ||--o{ stg_award : "BRN 낙찰 이력"
    mart_features_at_bid }o--|| stg_bid_notice : "공고 단위"
    mart_features_at_bid }o--|| mart_company_master : "BRN 단위"
```

**조인 키:**
- `BRN` (사업자등록번호 10자리) — 모든 BRN 데이터의 통합 키. 정규화 필수 (`pipeline.g2b_common.normalize_brn`)
- `bid_ntce_no` (공고번호 13자리) + `bid_ntce_ord` (차수) — 공고 단위 PK
- `dtil_prdct_clsfc_no` (세부품명번호 10자리) — 품목 분류

---

## 4. 피처 엔지니어링 — `mart_features_at_bid` 30 컬럼

### 4.0 설계 원칙

**PIT (Point-In-Time)** — 각 공고에 대해 그 공고 시점(`cutoff_date = bid_ntce_dt` 게시일) **이전 데이터만 집계**. 미래 정보 누설 방지 (leakage prevention).

```sql
-- 잘못된 예 (leakage)
SELECT COUNT(*) FROM stg_award WHERE bidwinnr_brn = 'X'
-- → 미래 낙찰 이력이 포함되어 라벨 누설이 발생함

-- 올바른 PIT 패턴
LEFT JOIN LATERAL (
    SELECT COUNT(*) FROM stg_award a
    WHERE a.bidwinnr_brn = p.brn
      AND a.fnl_sucsf_date < p.cutoff_date::date  -- ← 핵심
) env_pit ON true
```

**Candidate Pool** (`mart_features_at_bid`의 행 단위) — 전체 공고와 전체 BRN의 모든 조합을 생성하면 후보 수가 과도하게 커진다. 따라서 아래 3가지 후보 풀 정책 중 하나를 사용한다:
- `item` — 그 공고 품목(prefix4) 등록 BRN 전체
- `warm_only` — 환경공단 활동 BRN ∩ 등록 BRN. 후보 수는 작지만 환경공단 이력이 있는 BRN 중심으로 구성된다.
- `prefix_warm` — 그 공고 prefix4 등록 BRN ∩ warm 활동 BRN. 현재 기본값이며, 후보 규모와 커버리지의 균형을 맞춘 방식이다.

`scripts/build_features.py --pool prefix_warm` (default).

---

### 4.1 키 (PK + 라벨)
| 컬럼 | 타입 | 설명 |
|---|---|---|
| bid_ntce_no, bid_ntce_ord, brn | str | (공고 × BRN) PK |
| **is_winner** | bool | **타겟 (분류)** — 이 BRN이 이 공고에서 최종 낙찰 |
| participated_in_bid | bool | 응찰 여부 (5번 1순위 또는 1번 낙찰자) — leakage 위험 컬럼 (분류 학습 시 제외) |

**라벨 정의 SQL:**
```sql
-- is_winner: 1번 (낙찰자) 매칭
LEFT JOIN LATERAL (
    SELECT a.bidwinnr_brn AS brn FROM stg_award a
    WHERE a.bid_ntce_no = p.bid_ntce_no
      AND a.bid_ntce_ord = p.bid_ntce_ord
      AND a.bidwinnr_brn = p.brn
) a_final ON true
→ COALESCE(a_final.brn IS NOT NULL, false) AS is_winner

-- participated_in_bid: 5번 (1순위) 매칭
→ COALESCE(o_top1.brn IS NOT NULL, false) AS participated_in_bid
```

**분포 (실측, 학습 데이터 268k row):**
- `is_winner = TRUE` 비율 ≈ 0.16% (449 winners)
- `participated_in_bid = TRUE` 비율 ≈ 0.6%
- → 극심한 클래스 불균형이 있으므로 LightGBM 학습 시 `scale_pos_weight=154`로 자동 보정한다.

---

### 4.2 A. BRN 정적 피처 (7)

| 컬럼 | 출처 | 가설 |
|---|---|---|
| `corp_size` | mart_company_master | 중소·중견·대기업. 환경공단 발주는 중소 우대 정책 有 |
| `is_manufacturer` | mart_company_master | 자체 제조 BRN이 신뢰성 높음 (납품 안정성) |
| `region_code` | mart_company_master (2자리 시도) | 발주청과 같은 권역이면 운송비/서비스 유리 |
| `g2b_age_years` | mart_company_master.g2b_registered_at | `(cutoff_date - 등록일)/365.25`. 오래된 BRN = 신뢰성 |
| `female_ceo_flag` | mart_company_sr | 여성기업 자동판별 (대표자 성별) |
| `disabled_corp_flag` | mart_company_sr | 장애인기업 인증 |
| `social_corp_flag` | mart_company_sr | 사회적기업 인증 |
| `real_sr_flag` | derived | `disabled OR social` (실질SR — 자동판별 X) |

**g2b_age_years 계산:**
```sql
EXTRACT(EPOCH FROM (p.cutoff_date - m.g2b_registered_at::timestamptz))
  / (365.25 * 86400)
```

---

### 4.3 B. BRN 환경공단 누적 PIT (6)

> 과거 환경공단 낙찰 이력이 많을수록 향후 낙찰 가능성이 높아질 수 있다. 이 그룹은 BRN의 환경공단 거래 이력을 나타낸다.

LATERAL 서브쿼리 패턴:
```sql
LEFT JOIN LATERAL (
    SELECT
        COUNT(*) AS cnt,
        COALESCE(SUM(a.sucsfbid_amt), 0)::bigint AS amt,
        AVG(a.sucsfbid_rate)::numeric(6,3) AS avg_rate,
        COUNT(DISTINCT a.dminstt_cd) AS dminstt_cnt,
        SUM(CASE WHEN a.fnl_sucsf_date >= (p.cutoff_date - INTERVAL '1 year')::date
                 THEN 1 ELSE 0 END) AS recent_1y,
        EXTRACT(DAY FROM (p.cutoff_date - MAX(a.fnl_sucsf_date)::timestamptz))::int
            AS days_since
    FROM stg_award a
    WHERE a.bidwinnr_brn = p.brn
      AND a.fnl_sucsf_date IS NOT NULL
      AND a.fnl_sucsf_date < p.cutoff_date::date     -- ★ PIT 핵심
) env_pit ON true
```

| 컬럼 | 의미 | 값 범위 (실측) |
|---|---|---|
| `env_award_count_pit` | 환경공단 누적 낙찰 건수 | 0 ~ 25, p50=0, p90=2 |
| `env_award_amt_pit` | 누적 낙찰액 (KRW) | 0 ~ 수십억 |
| `env_avg_rate_pit` | 평균 낙찰률 (%) | 70 ~ 100, p50=88 |
| `env_dminstt_count_pit` | 거래한 환경공단 dminstt 수 | 0 ~ 10 (전국 권역 다양성) |
| `env_recent_1y_count_pit` | 최근 1년 낙찰 건수 | 0 ~ 10, 활동 모멘텀 |
| `days_since_last_award_pit` | 마지막 낙찰 후 경과일 | NULL (이력 없음) ~ 수년 |

**LightGBM Top Features (학습 결과):** `env_award_count_pit`, `env_avg_rate_pit` 가 상위 5위 안에. → **이 그룹이 가장 영향력 큼.**

---

### 4.4 C. BRN 응찰 패턴 PIT (4) — 리스크 지표

> 5번 개찰결과에서 1순위였지만 1번 낙찰자 데이터에서 다른 BRN이 최종 낙찰자로 기록된 경우는 자격검사 탈락 또는 시담 결렬 가능성을 의미한다. 이 패턴이 반복되는 BRN은 향후 최종 낙찰 단계에서 리스크가 있을 수 있다.

```sql
LEFT JOIN LATERAL (
    SELECT
        COUNT(*) FILTER (WHERE final_brn IS NOT NULL OR final_brn IS NULL) AS top1_cnt,
        COUNT(*) FILTER (WHERE final_brn IS NULL OR final_brn != p.brn) AS lost_cnt,
        ...
        SUM(CASE WHEN openg_dt >= (p.cutoff_date - INTERVAL '1 year')
                 AND (final_brn IS NULL OR final_brn != p.brn) THEN 1 ELSE 0 END)
            AS recent_lost
    FROM stg_opening_result o
    LEFT JOIN stg_award a USING (bid_ntce_no, bid_ntce_ord)
    WHERE o.winner_brn = p.brn
      AND o.openg_dt < p.cutoff_date     -- ★ PIT
) bid_pit ON true
```

| 컬럼 | 의미 | 시그널 |
|---|---|---|
| `bid_top1_count_pit` | 1순위 누적 횟수 | 활발도 |
| `bid_lost_count_pit` | 1순위였으나 최종낙찰 실패 | **위험** |
| `bid_lost_ratio_pit` | lost / top1 | **0.3 이상이면 검토 필요** |
| `bid_recent_lost_count_pit` | 최근 1년 탈락 | 최신 위험 |

**룰베이스 위험등급 임계값** (`pipeline/recommend_v2.py`):
```python
RISK_LOST_HARD: int = 3        # 누적 탈락 hard cap
RISK_LOST_RATIO: float = 0.30  # 비율 hard cap
RISK_RECENT_LOST: int = 2      # 최근 1년 hard cap
RISK_TOP1_SAFE: int = 3        # 안전 등급 진입 최소 top1
```

---

### 4.5 D. BRN × 품목 매칭 PIT (3) — 도메인 적합성

> BRN이 같은 품목군(prefix4)에서 자주 낙찰받았다면 해당 품목군에 대한 도메인 전문성이 높다고 볼 수 있다.

```sql
LEFT JOIN LATERAL (
    SELECT COUNT(*) AS cnt,
           AVG(a.sucsfbid_rate)::numeric(6,3) AS avg_rate
    FROM stg_award a
    JOIN stg_bid_notice b USING (bid_ntce_no, bid_ntce_ord)
    WHERE a.bidwinnr_brn = p.brn
      AND LEFT(b.dtil_prdct_clsfc_no, 4) = LEFT(p.item_code, 4)   -- 같은 prefix4
      AND a.fnl_sucsf_date < p.cutoff_date::date
) item_pit ON true
```

| 컬럼 | 의미 |
|---|---|
| `brn_item_award_count_pit` | 같은 prefix4 누적 낙찰 |
| `brn_item_avg_rate_pit` | 같은 prefix4 평균 낙찰률 |
| `main_prdct_match` | BRN의 `main_dtil_prdct_cd` (조달업체 CSV) == 공고 품목 (10자리 일치) |

**LightGBM Top Features**: `brn_item_award_count_pit` 가 1위. → 도메인 전문성이 가장 강력한 시그널.

---

### 4.6 E. BRN × 권역 PIT (1)

```sql
LEFT JOIN LATERAL (
    SELECT COUNT(*) AS cnt FROM stg_award a
    WHERE a.bidwinnr_brn = p.brn
      AND a.dminstt_cd = p.dminstt_cd     -- 같은 발주청
      AND a.fnl_sucsf_date < p.cutoff_date::date
) dminstt_pit ON true
```

| 컬럼 | 의미 |
|---|---|
| `brn_dminstt_award_count_pit` | 그 발주청 직접 거래 누적 (관계 강도) |

---

### 4.7 F. 공고 측 (7) — 컨텍스트

PIT 불필요 (공고 자체 메타).

| 컬럼 | 의미 | 결측 |
|---|---|---|
| `presmpt_prce` | 사정가격 (KRW) | 가능 |
| `asign_bdgt_amt` | 배정예산 (KRW) | 가능 |
| `cntrct_cncls_mthd_nm` | 계약방식 (일반/제한/수의/지명) | NOT NULL |
| `bid_month` | 1~12 (계절성) | NOT NULL |
| `bid_quarter` | 1~4 | NOT NULL |
| `bid_dminstt_cd` | 발주청 (categorical, env_corp 10개 + env_domain 26개) | NOT NULL |
| `bid_dtil_prdct_no` | 세부품명번호 (10자리) | 가능 |

**LightGBM 처리**: `cntrct_cncls_mthd_nm`, `bid_dminstt_cd`, `bid_dtil_prdct_no` 는 high-cardinality categorical → `categorical_feature=` 인자로 전달.

---

### 4.8 G. 시장 구조 PIT (3)

> 해당 품목의 공급 업체 수가 많으면 경쟁 강도가 높아져 개별 BRN의 낙찰 가능성이 낮아질 수 있다. 반대로 최근 미낙찰 비율이 높으면 신규 후보가 낙찰될 여지가 커질 수 있다.

| 컬럼 | 의미 |
|---|---|
| `item_pool_density_pit` | 그 품목 등록 BRN 수 (시장 깊이) |
| `item_recent_unmet_pit` | 최근 1년 미낙찰 (유찰) 비율 |
| `item_top1_concentration_pit` | 상위 BRN 집중도 (HHI 유사) |

---

### 4.9 메타 컬럼

| 컬럼 | 의미 |
|---|---|
| `cutoff_date` | PIT 기준 시점 (= 공고 게시일 `bid_ntce_dt`) |
| `last_synced_at` | 마트 빌드 시점 (audit) |

---

### 4.10 빌드 파이프라인

```
mart_features_at_bid 빌드 흐름:

1. tmp_candidate_pool 생성 (CTE 또는 임시테이블)
   ├─ pool='prefix_warm': stg_bid_notice ⨉ (mart_item_supply ∩ warm_brns)
   └─ 환경공단 공고 한정 + cutoff_date = bid_ntce_dt

2. SQL_INSERT_FEATURES — 단일 INSERT ... SELECT
   ├─ tmp_candidate_pool 좌측에 두고
   ├─ LATERAL 서브쿼리 6개 (env_pit, bid_pit, item_pit, dminstt_pit, market_pit + a_final/o_top1 라벨)
   └─ TRUNCATE → INSERT (full rebuild, idempotent)

3. 인덱스 (PK 외)
   - idx_features_brn (BRN 검색)
   - idx_features_cutoff (시계열)
   - idx_features_item (품목 검색)
   - idx_features_winner (positive sample 추출)
```

**실행:**
```bash
uv run python scripts/build_features.py --pool prefix_warm
# 약 30초~1분, 343,019 rows / 1,359 BRN / 2,702 bids
```

---

### 4.11 LightGBM 학습 결과 — Top 15 Feature Importance (gain)

학습 결과 참고용 (실제 `artifacts/feature_importance.csv`):

| 순위 | 피처 | 그룹 |
|---|---|---|
| 1 | `brn_item_award_count_pit` | D 도메인 적합성 |
| 2 | `env_award_count_pit` | B 누적 |
| 3 | `env_avg_rate_pit` | B 누적 |
| 4 | `brn_dminstt_award_count_pit` | E 권역 |
| 5 | `env_recent_1y_count_pit` | B 누적 (최근) |
| 6 | `presmpt_prce` | F 공고 |
| 7 | `g2b_age_years` | A 정적 |
| 8 | `bid_top1_count_pit` | C 활발도 |
| 9 | `item_pool_density_pit` | G 시장 |
| 10 | `bid_lost_ratio_pit` | C 위험 |

→ **D > B > E > C 순으로 영향력이 크다.** SR 인증(A)은 중간 수준이다. LightGBM은 SR 정책 가점을 직접 학습하지 않으므로 운영 랭킹에서는 룰베이스로 보강한다.

---

### 4.12 결측 / 함정

- **psycopg2 BOOLEAN → Python object** — pandas로 읽으면 `dtype=object`가 된다. 학습 직전에 `int8`로 캐스팅해야 한다. (`scripts/train_baseline.py` `BOOL_COLS` 참조)
- **avg_rate NULL** — 낙찰 이력이 없는 BRN에서 발생한다. `fillna(0)` 처리하거나 missing 상태로 두면 LightGBM이 자동 처리한다.
- **g2b_age_years NULL** — 등록일이 없는 BRN에서 발생한다. 전체의 약 5% 수준이다.
- **main_prdct_match** — `m.main_dtil_prdct_cd IS NULL`인 경우 `COALESCE(... = ..., false)`로 처리한다.
- **leakage 위험** — `participated_in_bid` 컬럼을 학습에 사용하면 라벨 누설이 발생한다. `train_baseline.py DROP_COLS`에 포함되어 있다.

---

## 5. 추천 워크플로우 (v2 운영 모드)

```
사용자 입력 (RecommendV2Request)
   │ {item_keyword, budget_million_won, sr_filter, top_k}
   ▼
[Stage 1] retrieve  (pipeline/recommend_v2.retrieve)
   ├─ 키워드 → KEYWORD_FILTERS dict (11개) → (prefix4_list, name_regex)
   ├─ candidate_brns CTE
   │  ├─ (a) mart_item_supply ∩ warm_brns (등록 BRN)
   │  └─ (b) UNION 실제 매칭 prefix4+regex 낙찰 BRN (등록 미반영 보완)
   └─ sr_filter hard AND filter
   ▼
[Stage 2] rank  (pipeline/ranker.RuleRanker)
   ├─ 4축 가중합 (sr 0.35 + track 0.30 + price 0.20 + supply 0.15)
   ├─ SR soft floor: n_sr_certified ≥ 3 → sr=0 BRN -1.0 demote
   └─ ★ 교체 지점: ranker=LGBMRanker() 구현체로 전환 가능
   ▼
[Enrich] (top_k 만)
   ├─ 시장 baseline (전체 + 유사 규모)
   ├─ BRN 낙찰률 분포 (전체 + 유사 규모) ← 외삽 방지
   ├─ 1순위 탈락 이력
   ├─ 최근 낙찰 5건
   ├─ 유사 발주 사례
   └─ 시각화 raw
   ▼
[KPI + Compliance + 정렬]
   ▼
RecommendV2Response → 프론트
```

---

## 6. 코드 진입점 — 어디부터 보면 좋나

| 목적 | 파일 |
|---|---|
| 시스템 전체 이해 | `CLAUDE.md` (특히 §11 §12 §13) |
| 추천 로직 (메인) | `pipeline/recommend_v2.py` |
| 룰베이스 점수 (Stage 2) | `pipeline/ranker.py` (Ranker Protocol + RuleRanker) |
| 키워드 매핑 | `pipeline/item_keywords.py` |
| API 엔드포인트 | `api/main.py` |
| 응답 스키마 | `api/schemas.py` |
| 정책 상수 (SR floor 등) | `pipeline/policy.py` |
| 수집 (이미 동작) | `scripts/ingest_*.py`, `pipeline/g2b_*.py` |
| 마트 빌드 | `scripts/build_stg.py`, `scripts/build_features.py` |
| 학습 (참고용) | `scripts/train_baseline.py` (LGBM Classifier) |
| 테스트 (27개) | `tests/test_recommend_v2_pure.py` |
| 프론트 메인 | `frontend/src/App.tsx` |
| 디자인 목업 | `analysis/dashboard_mockup_v2_1.html` |

---

## 7. 데이터 dump / restore

### Dump (운영자 측)
```bash
pg_dump eco -F c -f eco_dump_$(date +%Y_%m_%d).dump
# 산출 파일 약 ~50MB. Drive/USB 공유.
```

### Restore (팀원 측)

별도 공유받은 dump 파일을 프로젝트의 `data/dumps/` 에 두고 복원한다 (`data/` 는 gitignored).

```bash
# 1. dump 파일 위치 (다운로드 위치에 따라 조정)
mkdir -p data/dumps
mv ~/Downloads/eco_2026_05_06.dump data/dumps/

# 2. DB 생성 + 복원
createdb eco
pg_restore --no-owner -d eco data/dumps/eco_2026_05_06.dump

# 3. 검증
psql eco -c "SELECT COUNT(*) FROM mart_company_master;"
# → 65,000+ 행이 나오면 정상
```

### G2B 신규 적재 (선택 — 본인 키 보유 시)
```bash
# 14번 → 1번 → 5번 → 9번 → build_stg → build_features 순
uv run python scripts/ingest_bid_notice.py --start 2025-05-01 --end 2026-05-01
uv run python scripts/ingest_award.py --skip-empty
uv run python scripts/ingest_opening.py --skip-empty
uv run python scripts/ingest_prepar.py --skip-empty
uv run python scripts/build_stg.py
uv run python scripts/build_features.py
```

---

## 8. FAQ

**Q. LGBM 학습 결과를 운영 랭킹에 바로 사용하지 않는 이유는?**
A. CLAUDE.md §13 참조. 현재 운영 화면은 공고가 확정되기 전의 사전 탐색 모드다. 반면 LGBM 모델은 특정 공고와 BRN 조합을 입력으로 학습되어 두 입력 구조가 맞지 않는다. 이후 synthetic bid 생성 또는 회귀 모델 전환 방식으로 운영 랭커에 연결할 예정이다.

**Q. agency_tier 가 뭐?**
A. `env_corp` (한국환경공단 10), `env_domain` (수자원공사+상수도+환경부 26), `other` (그 외). 풀 확장용. `pipeline.g2b_common.agency_tier_for()` 매핑.

**Q. PIT란 무엇인가?**
A. Point-In-Time의 약자다. 각 공고 시점 이전 데이터만 집계하여 미래 정보 누설(leakage)을 방지한다. `mart_features_at_bid`의 모든 `*_pit` 컬럼은 `cutoff_date` 이전 데이터로만 계산된다.

**Q. 새 키워드는 어떻게 추가하는가?**
A. `pipeline/item_keywords.py`의 `KEYWORD_FILTERS` dict에 `(prefix4_list, name_regex)`를 추가한다. 추가된 키워드는 백엔드 응답에 자동 반영되며, 프론트의 키워드 칩도 `useKeywords` 훅을 통해 갱신된다.

**Q. 4축 가중치는 어디서 변경하는가?**
A. `pipeline/ranker.py`의 `DEFAULT_WEIGHTS`에서 변경한다. 단, `sr_diversity`는 사회적가치법 하한에 따라 0.20 이상이어야 하며, 관련 상수는 `pipeline/policy.py`에 정의되어 있다.

**Q. 외삽 경고는 언제 표시되는가?**
A. BRN의 과거 거래 중 입력 예산 ±50% 범위에 해당하는 사례가 없을 때 표시된다. 이 경우 `ExpectedPrice.is_extrapolated=True`가 되며, 카드에는 경고 배지로 표시된다.

**Q. 의무비율 20%의 근거는 무엇인가?**
A. 조달사업법 시행령 제24조의 사회적가치 우선구매 조항을 기준으로 한다. 관련 값은 `pipeline/policy.SR_LEGAL_FLOOR_PCT = 20.0`으로 단일 정의되어 있다.

---

## 9. 개발 명령

```bash
# 테스트
uv run python -m unittest tests.test_recommend_v2_pure -v   # 27개

# 린트
uvx ruff check pipeline/ api/ tests/

# 백엔드 + 프론트 띄우기
uv run uvicorn api.main:app --reload --port 8000
cd frontend && npm run dev

# curl 테스트
curl -X POST http://localhost:8000/api/v2/recommend -H 'Content-Type: application/json' \
  -d '{"item_keyword":"하수처리용 펌프","budget_million_won":800,"sr_filter":{"social_corp":false,"female_ceo":false,"disabled_corp":false},"top_k":3}'
```

---

## 10. 주의사항 (CLAUDE.md §9)

- **G2B_SERVICE_KEY** 는 `.env` 만 — git commit 금지
- **새 라이브러리 임의 추가 금지** — 사용자 확인 필수
- **PostgreSQL 스키마 변경 시** `sql/<날짜>_<설명>.sql` 마이그레이션 파일 필수
- **8 키워드 외 자연어 free-text 매핑 금지** — `KEYWORD_FILTERS` dict 만
- **calibration 안 된 ML 점수 raw 노출 금지** — 운영 카드는 등급(A/B/C) 또는 순위만
- **공무원 사용자에게 ingest 트리거 권한 X** — 운영팀 책임

---

문의 사항은 PR 코멘트로 남기거나 운영팀에 전달한다.
