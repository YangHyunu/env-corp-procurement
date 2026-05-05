# Brooks-Lint Review (재실행 — 확장된 범위)

**Mode:** PR Review (re-run after 6 new commits landed)
**Scope:** branch `feat/scoring-mvp` vs `main` — 62 files / +18,624 / −70. Sampled toward highest-risk new Python: `pipeline/recommend_v2.py` (564), `pipeline/ranker.py` (127), `pipeline/item_keywords.py` (49), `api/schemas.py` (233). Skipped: `frontend/package-lock.json` and `uv.lock` (generated), `app/streamlit_app.py` (deprecated per CLAUDE.md §5), React `ui/*` shadcn primitives (vendor), prior-reviewed `pipeline/scoring.py` + `scripts/demo_scoring.py`.
**Trend:** 64 → 58 (−6) — first re-run

PR이 이번 주 +18k줄로 폭발했고, 룰 기반 추천 엔진이 두 모듈에 중복 구현되며 동시에 SQL 합성 패턴·연결 관리·타입 계약이 모두 일관성을 잃었다 — Brooks의 Conceptual Integrity 시그널이 켜진 시점.

> **Note:** PR > 500 lines is itself a Change Propagation signal — review의 한 번에 보일 수 없는 사이즈. 7 commits 모두 별도 PR로 쪼갰으면 각 commit별 리스크가 훨씬 명확했을 것.

---

## Findings

### 🔴 Critical

**Knowledge Duplication — RuleRanker는 `pipeline/scoring.py`의 두 번째 사본**
- **Symptom:** `pipeline/ranker.py:19-25` (`DEFAULT_WEIGHTS`, `SR_LEGAL_FLOOR`)와 `pipeline/scoring.py:36-42`가 동일한 값. `_validate_weights`는 `ranker.py:39-46`과 `scoring.py:99-106`에 토씨 하나 다르지 않게 재구현. 4축 산식 (rank/percentile, `clip(0,3)/3.0`, `0.6 * norm_count + 0.4 * norm_bid_rate`, unit_price 역백분위), SR soft-floor `composite_score -= 1.0` (line 110 vs 182)도 동일. `ranker.py` docstring이 직접 인정함: "4축 가중합 — pipeline.scoring 의 v1 로직 이식."
- **Source:** Hunt & Thomas — *The Pragmatic Programmer*, DRY; Brooks — *The Mythical Man-Month*, Ch. 4: Conceptual Integrity
- **Consequence:** 가중치 또는 floor 임계 조정 시 두 모듈을 함께 수정해야 한다 — 잊으면 v1 API (`/api/recommend`)와 v2 (`/api/v2/recommend`)가 같은 입력에 대해 다른 순위를 반환한다. 분기 1회 가중치 재검토(CLAUDE.md §12)가 곧 silent regression의 진앙이 될 수 있다. CLAUDE.md §11이 명시한 "Stage 2 swap point"라는 v2의 핵심 약속도 무너진다 — RuleRanker 자체가 swap-out 대상인데 v1 동치를 두 곳에 박아놓으면 LGBMRanker로 갈 때 어느 쪽을 기준으로 학습해야 하는지 모호해진다.
- **Remedy:** `pipeline/ranker.py`의 `RuleRanker`만을 정통(canonical)으로 남기고, `pipeline/scoring.py`는 (a) 완전 제거(v1 API 엔드포인트가 `RuleRanker`를 직접 사용하도록 `api/main.py:115`만 갈아끼움), 또는 (b) `score()` 함수가 내부적으로 `RuleRanker().score(...)`를 위임하는 얇은 어댑터로 축소. 어떤 쪽이든 가중합·SR-floor·검증 로직은 한 군데에서만 변경 가능하도록.

### 🟡 Warning

**Cognitive Overload — `enrich()`가 121줄에 5개 phase 혼합**
- **Symptom:** `pipeline/recommend_v2.py:322-443` 한 함수 안에서 (1) brn 리스트 추출 + 4개 SQL helper 호출, (2) 예상가 점추정/구간/시장편차, (3) 리스크 등급+dormancy, (4) 공급 안정성+g2b_age, (5) 시각화 raw + DTO 조립이 직렬로 진행. 1개 BRN당 ~80줄 DTO build가 for 루프 안에 인라인. 심각도 가이드는 > 50줄 + nesting 2-3 = Warning 경계.
- **Source:** Fowler — *Refactoring*, Long Method; McConnell — *Code Complete*, Ch. 7
- **Consequence:** "예상가 fallback 정책 변경", "dormancy 기준 24개월 → 18개월", "tier 컷오프 조정" 같은 단일 도메인 변경이 모두 같은 함수 본문을 수정하게 만든다 — diff에서 책임이 섞이고, 이 함수에 대한 단위 테스트는 모든 SQL 모킹을 요구하게 되어 사실상 작성 불가. CLAUDE.md §11 카드 스펙이 늘어날수록 함수도 비례해서 비대해진다.
- **Remedy:** 5 phase를 작은 함수로 분리: `_make_expected_price(c, dist, market, budget_won)`, `_make_risk(c, rs)`, `_make_supply_stability(c)`, `_make_charts(dist)`. `enrich()`는 brn 추출 + 4개 SQL → loop에서 각 helper 호출 + DTO 조립으로 ~30줄까지 축소. 각 helper가 독립 테스트 대상이 됨.

**Dependency Disorder — `psycopg2.connect()`가 한 `recommend()` 호출당 8회 + connect/cursor 보일러플레이트 7곳 복붙**
- **Symptom:** `pipeline/recommend_v2.py`에서 `psycopg2.connect(dsn)` 호출이 `retrieve` (line 94), `_market_baseline` (124), `_brn_rate_distribution` (156), `_brn_risk_signals` (183), `_brn_recent_awards` (206), `_precedents` (234), `compute_kpi` (477), `_cutoff` (522) — 8개 helper에서 각각 새 connection을 연다. 각 helper는 `with psycopg2.connect(dsn) as conn: with conn.cursor(...) as cur: ...` 동일 패턴을 복사.
- **Source:** Martin — *Clean Architecture*, DIP; Hunt & Thomas — *Pragmatic Programmer*, DRY; Ousterhout — *A Philosophy of Software Design*, Ch. 5: Information Leakage
- **Consequence:** (a) 한 요청당 connect 8회 = local Postgres에서 80~240ms 오버헤드 — 사용자가 인지할 정도. 운영 VM(클라우드)에서 RTT 증가하면 더 심함. (b) helper 간 트랜잭션 보장 없음 — `_market_baseline` 호출 시점과 `_brn_rate_distribution` 시점 사이 ingest가 중간에 들어오면 일관성 깨짐 (현재 주 1회 batch라 실무에서는 잘 안 일어나지만, Phase 3 자동화 시 위험). (c) "DSN을 어떻게 다루는가"라는 결정이 8군데 분산 — Connection Pool 도입 시 8군데 모두 수정 필요. (d) DB 연결 자체가 모든 helper의 도메인 로직과 섞여 테스트 시 모킹 표면이 8배.
- **Remedy:** `_DbExec` 헬퍼 또는 `with_conn(dsn) as conn` context manager 하나를 두고 helper 함수들이 `conn`을 인자로 받도록 변경. `recommend()`가 entry point에서 한 번만 `psycopg2.connect`해서 모든 helper에 전달. 이상적으로는 last review에서 제안한 `PoolRepository` Protocol을 확장한 `RecommendQueries` Protocol 하나에 8개 SQL을 메소드로 묶고, 구현체가 connection 수명을 책임지는 구조.

**Hyrum's Law / Information Leakage — `RETRIEVE_SQL.format(sr_clause=...)` SQL 동적 합성 패턴**
- **Symptom:** `pipeline/recommend_v2.py:93` — `sql = RETRIEVE_SQL.format(sr_clause=_build_sr_clause(sr_filter))`. `_build_sr_clause` (lines 81-86)는 현재 고정 리터럴(`"AND mcs.female_ceo_flag"` 등)만 반환하므로 SQL injection은 없지만, `.format()`이 SQL 텍스트와 parameterized bind(`%(prefix4)s`, `%(name_regex)s`)와 같은 쿼리 안에 혼재.
- **Source:** Winters et al. — *Software Engineering at Google*, Ch. 1: Hyrum's Law; Ousterhout — *A Philosophy of Software Design*, Ch. 5: Information Hiding
- **Consequence:** 다음 contributor가 "지역 필터도 추가하자"며 `_build_sr_clause`에 `f"AND region='{sr_filter['region']}'"`을 추가하는 순간 classic SQL injection. 코드베이스가 가르치는 패턴이 "SQL은 `.format()`으로 조립한다"가 됐기 때문에 실수의 비용이 매우 낮다. 또한 IDE/lint가 SQL injection을 경고할 수단이 거의 없음 (psycopg2 cursor.execute에 들어가기 전 string concatenation).
- **Remedy:** 가변 절은 항상 placeholder + bind variable 또는 `psycopg2.sql.SQL/Identifier/Composed`로 작성. 현재의 `sr_clause`는 boolean 인덱스 키 3개로 고정이므로, `sql`을 그대로 두고 WHERE에 `AND (NOT %s OR mcs.female_ceo_flag)` 식 트릭으로 binds만 추가하면 동적 합성 자체가 사라짐. 또는 `psycopg2.sql.Composed([SQL("AND mcs.female_ceo_flag") if ...])`. 어느 쪽이든 `.format()`은 SQL 본문 영역에서 추방.

**Domain Model Distortion — `recommend()`가 `dict[str, Any]` 반환, 강타입 `RecommendV2Response`와 비연결**
- **Symptom:** `pipeline/recommend_v2.py:530` `def recommend(req) -> dict[str, Any]`. `api/schemas.py:219` `class RecommendV2Response(BaseModel)`이 같은 모양을 강타입으로 정의하지만 둘 사이에 컴파일 타임 연결 없음. `enrich()` (line 420-442)가 dict literal로 21개 필드를 직접 build, FastAPI가 응답 시점에 Pydantic으로 검증.
- **Source:** Evans — *Domain-Driven Design*, Ubiquitous Language; Martin — *Clean Architecture*, LSP의 정신 (계약 일관성); Fowler — *Refactoring*, Data Class
- **Consequence:** producer가 필드 하나를 빠뜨리거나 오타 (`expected_price` vs `excpected_price`)를 내도 mypy/IDE가 잡지 못한다. 발견은 "production 응답이 422" 또는 "frontend에서 undefined" 시점. CLAUDE.md §11이 명시한 응답 스키마 11개 필드가 dict literal에 박혀 있어 schema가 진실의 근원이 아니다.
- **Remedy:** `recommend()` 시그니처를 `-> RecommendV2Response`로 바꾸고 내부에서 dataclass / Pydantic 모델을 직접 build. `enrich()` 또한 `list[RecommendationV2Item]`을 반환. FastAPI가 `RecommendV2Response`를 응답 모델로 그대로 사용 가능 (`@app.post(..., response_model=RecommendV2Response)`).

**Knowledge Duplication — SR 법정 floor가 4 군데에 다른 표기로 박혀 있음**
- **Symptom:** 같은 "사회적 가치 우선구매 촉진법 제7조 20%" 값이 4 위치에 등장 — `pipeline/scoring.py:42` `SR_LEGAL_FLOOR = 0.20`, `pipeline/ranker.py:25` `SR_LEGAL_FLOOR = 0.20`, `api/schemas.py:10` `Field(ge=0.20)`, `pipeline/recommend_v2.py:516-517` `obligation_threshold_pct: 20.0` + `obligation_met: pct >= 20.0`. 같은 법조항이 0.20 (가중치 fraction) vs 20.0 (퍼센트)로 단위까지 다름.
- **Source:** Hunt & Thomas — *Pragmatic Programmer*, DRY: Single Source of Truth
- **Consequence:** 법령 개정 시 4 곳 + Pydantic Field literal까지 수정 필요. 단위가 달라 `0.20` 검색만으로는 모두 못 찾는다 — `20.0`도 검색해야 함. 현재 `SR_LEGAL_FLOOR = 0.20`은 두 모듈에 중복 정의되어 있어 한 쪽만 0.18로 바뀌면 같은 입력이 한 API에서는 거절되고 다른 API에서는 통과한다.
- **Remedy:** `pipeline/legal_constants.py` (또는 `pipeline/policy.py`) 한 모듈에 `SR_LEGAL_FLOOR_PCT: float = 20.0`, `SR_LEGAL_FLOOR_FRACTION: float = SR_LEGAL_FLOOR_PCT / 100.0` (혹은 그 역). 모든 모듈이 import만 하도록 변경. Pydantic `Field(ge=...)`는 literal 요구이므로 module-level constant를 `model_config`의 `json_schema_extra`로 넘기거나, 모델 빌드 시점에 검증하도록 우회.

### 🟢 Suggestion

**Cognitive Overload — 도메인 임계가 모두 무명 매직 넘버**
- **Symptom:** `_risk_grade` (line 245-253)의 `lost >= 3`, `ratio >= 0.30`, `recent_lost >= 2`, `top1 >= 3`; `_tier` (256-263)의 `>= 0.6`, `>= 0.3`; `_dormant_months`의 `30.4` (line 273); dormancy threshold `>= 24` (line 391); precedent budget `0.5x`/`1.5x` (line 239); compliance `20.0` (line 517).
- **Source:** McConnell — *Code Complete*, Ch. 12: Magic Numbers
- **Consequence:** CLAUDE.md §11 "리스크 등급 4단계" 표가 코드 내부 임계와 동기화되어 있는지 확인하려면 매번 코드와 docs를 대조 필요. 임계 변경(이번 분기 검토)이 docs 업데이트를 흔적 없이 빠뜨리기 쉽다.
- **Remedy:** `pipeline/recommend_v2.py` 상단에 named constants — `RISK_LOST_HARD = 3`, `RISK_LOST_RATIO = 0.30`, `RISK_RECENT_LOST = 2`, `TIER_A_CUTOFF = 0.6`, `TIER_B_CUTOFF = 0.3`, `DORMANT_MONTHS = 24`, `PRECEDENT_BUDGET_LO = 0.5`, `PRECEDENT_BUDGET_HI = 1.5`, `MONTH_DAYS = 30.4`. CLAUDE.md §11 표를 docstring 형태로 같이 묶으면 single source 효과.

**Silent Exception — `except Exception: pass` (`pipeline/recommend_v2.py:402`)**
- **Symptom:** `g2b_age` 계산이 실패하면 조용히 `g2b_age = None`. `g2b_registered_at`이 미래 datetime이거나 잘못된 타입일 때 (mart 빌드 버그 등) 진단 흔적이 전혀 남지 않음.
- **Source:** McConnell — *Code Complete*, Defensive programming pitfalls; *Pragmatic Programmer*, Topic 24: "Dead Programs Tell No Lies"
- **Consequence:** 추천 카드의 "G2B 등록 X년" 표기가 임의로 비어 있어도 alert 없음 — 운영 데이터 quality 회귀가 들키지 않음.
- **Remedy:** 최소 `logger.warning("g2b_age compute failed for brn=%s reg=%s", brn, reg, exc_info=True)`. 더 좋은 건 예외 종류를 명시 (`except (TypeError, ValueError)`)하고, 실제 unexpected는 그대로 raise.

---

**Recommended fix order:** (1) Knowledge Duplication — `pipeline/scoring.py`/`pipeline/ranker.py` 통합이 다른 리팩토링의 전제; (2) `SR_LEGAL_FLOOR` 단일화 — 법령 변경 시 사고를 막는 가장 작은 PR; (3) `enrich()` 분해 + tests — 테스트 추가가 가능한 형태로 자르기; (4) Connection 통합 / SQL 합성 패턴 정리; (5) `recommend()` 강타입 반환; (6) 명명 상수 + 로깅 정리.

## Summary

가장 시급한 건 룰 기반 추천 로직의 이중 구현 정리 — `RuleRanker`와 `scoring.py`가 같은 결정을 두 군데서 내리는 한 v2 swap point가 약속을 지키지 못한다. 그 다음은 connect 보일러플레이트 + SQL 합성 패턴 통합인데, 이건 last review의 DIP 권고(`PoolRepository`)와 합쳐 `RecommendQueries` Protocol 한 번에 푸는 게 가장 경제적. 직전 리뷰의 Coverage Illusion(테스트 0건)은 코드량이 ~1500줄 더 늘어나며 더 위험해진 채로 그대로 남아있음 — 본 라운드에서는 신규 발견에 집중했지만 trend 단어로 반영.
