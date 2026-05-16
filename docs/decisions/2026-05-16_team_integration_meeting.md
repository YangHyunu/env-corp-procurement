# 팀 통합 회의 안건 — 2026-05-16

> 본 문서는 회의 **전** 의사결정 자료다. 결정은 회의 종료 시점에 이 문서 하단 "결정 기록" 섹션에 적어 PR 으로 커밋한다. 후속 코드 통합은 결정값을 근거로 별도 PR.

## 회의 목표 (40분)

다음 4개 결정 분기를 합의한다. 합의 안 되는 항목은 "다음 회의로 이월" 로 기록.

| ID | 주제 | 결정 종류 |
|---|---|---|
| D1 | entropy 신호 처리 방식 | 정책 + 코드 영향 |
| D2 | AI 클러스터링 재개 여부 | 로드맵 |
| D3 | 팀원 ranker 변형 통합 전략 | 코드 통합 |
| D4 | 가중치 / 정책 변경 권한 | 운영 정책 |

---

## D1 — entropy 신호 처리 방식

### 배경
후보 풀(retrieve 결과) 4축 분포의 entropy 가 낮으면 후보들이 한 점에 몰려 있다는 뜻 → 차별화 어려움. 높으면 분산이 큼 → 의미 있는 점수 차이 가능. 이 신호를 어디에 쓸지 정해야 한다.

### 옵션

**옵션 A — 보조 KPI (추천)**
- entropy 값을 `KpiV2.pool_entropy` 에 추가하고 카드 헤더 KPI 에 표시
- 점수·랭킹·tier 에는 영향 없음
- 코드 영향: `pipeline/ranker.py` 신규 함수 1개, `api/schemas.py`/`pipeline/recommend_v2.py:678` 채움, 프론트 KPI 1개
- 위험: 거의 없음. 사용자가 entropy 의미 모를 가능성 — UI 툴팁 필요

**옵션 B — 가중치 동적 보정**
- entropy 낮을 때 `RuleRanker` 가중치 조정 (예: `track_record` 비중 ↑, `price_competitiveness` 비중 ↓)
- 코드 영향: `RuleRanker.__init__` 시그니처 + `pipeline/policy.py` 보정 테이블 상수
- 위험: 회귀 baseline 크게 변함. SR floor (0.20) 하한 보장 어려워짐 — `_validate_weights` 강화 필요. calibration 부재로 의사결정 영향 예측 어려움

**옵션 C — 사용 안함**
- entropy 분석 자체는 분석 보고서에만 사용
- 코드 변경 0

### 우리 추천
**A.** 점수에 영향 없이 신호만 노출. 추후 데이터 쌓이면 B 검토.

### 결정에 필요한 정보 (회의 전 준비)
- entropy 값 분포 — 운영 8 키워드 × 현재 후보 풀 측정 (스크립트 `scripts/dump_recommend_baseline.py` 실행 후 후속 분석)
- KPI 카드 슬롯 여유 — 프론트 디자인 측 확인

### 영향 파일 (옵션별)
| 옵션 | 파일 |
|---|---|
| A | `pipeline/ranker.py` (+ `compute_pool_entropy`), `api/schemas.py:80` `KpiV2`, `pipeline/recommend_v2.py:678` `compute_kpi`, `frontend/src/lib/types.ts`, `frontend/src/components/KpiCard.tsx` |
| B | A 의 모든 파일 + `pipeline/ranker.py:21` `DEFAULT_WEIGHTS` 로직 변경, `pipeline/policy.py` 보정 테이블 |
| C | — |

---

## D2 — AI 클러스터링 재개 여부

### 배경
CLAUDE.md §13 에 "보류 (Phase 3 장기)" 로 결정됨. 사유: 데이터 양 부족(449 winners), 의사결정 critical 아님. 현재 코드에는 스텁만 남음 — `KpiResponse.cluster_count: int | None`, `scoring.axes.cluster_fit = 0.5`. 회의에서 재개 신호가 있는지 확인.

### 옵션

**옵션 A — 그대로 유지 (추천)**
- §13 보류 결정 유지
- 코드 변경 0
- 추후 Two-Tower 임베딩과 함께 Phase 3 진입 시 재논의

**옵션 B — 작은 PoC**
- 후보 풀(retrieve 결과)에 대해 KMeans 같은 가벼운 군집화 → `cluster_count` 만 채움
- 운영 점수에 안 들어감, KPI 표시만
- 코드 영향: `scripts/cluster_pool.py` (신규), `api/main.py:260` `cluster_count` 채움
- 새 라이브러리: scikit-learn 은 이미 pyproject 에 있음. **umap-learn / hdbscan 은 추가 필요 — CLAUDE.md §9 게이트**

**옵션 C — Phase 2 재설계**
- BRN 임베딩 학습부터 시작 → 큰 PR 별도, 별도 PoC 단계 필요

### 우리 추천
**A.** 운영 신호 부재. Phase 3 에서 임베딩과 묶어서 다시 논의.

### 영향 파일 (옵션별)
| 옵션 | 파일 |
|---|---|
| A | — |
| B | `scripts/cluster_pool.py` (신규), `api/main.py:260`, 의존성 합의 시 `pyproject.toml` |
| C | 별도 spec doc + Phase 3 trail |

---

## D3 — 팀원 ranker 변형 통합 전략

### 배경
팀원이 별도 브랜치에서 ranker 변형(LGBMRanker 후보 또는 다른 점수 로직) 작업 중. 회의에서 변경분의 크기·테스트 통과율·운영 신호를 보고 통합 방식을 정한다.

### 옵션

**옵션 A — base 유지 (추천 가능)**
- 현재 `feat/scoring-mvp-teambase` 그대로 운영
- 팀원 변경분은 별도 PR 로 후속 처리 (review 단계)
- 위험: 낮음. 운영 연속성 보장

**옵션 B — LGBMRanker swap**
- `pipeline/ranker.py` 에 `LGBMRanker` 클래스 추가, `artifacts/lgbm_baseline.txt` 로드
- 환경변수 또는 request flag 로 ranker 선택 (`pipeline/recommend_v2.py:165` `rank()`)
- `RecommendationV2Item.ml_score` 필드 채움 (`api/schemas.py:219` 이미 자리 잡힘), `score_used="ml"`
- 카드 UI 에 ml_score 보조 배지 — **단 raw probability 노출 금지** (CLAUDE.md §9, §11 "calibration 안 된 ML 점수 raw 노출 금지"). 등급 / 순위만
- 위험: 학습 데이터 한계(449 winners). HR@5 41% 운영 가능성 사용자와 합의 필요

**옵션 C — base 일부 revert + 통합**
- 회의에서 어떤 커밋 revert 인지 확정 필요
- 위험: 높음. 27 unit tests + 회귀 baseline 둘 다 검증 필수

### 결정에 필요한 정보 (회의 전 준비)
- 팀원 브랜치 diff 사이즈 (`git diff main..teammate-branch --stat`)
- 팀원 측 테스트 통과율
- 팀원 측 운영 신호(있다면) — 어떤 키워드에서 룰베이스와 다르게 동작하는가

### 영향 파일 (옵션별)
| 옵션 | 파일 |
|---|---|
| A | — (후속 PR 처리) |
| B | `pipeline/ranker.py` (+ `LGBMRanker`), `pipeline/recommend_v2.py:42` import, `pipeline/recommend_v2.py:165` `rank()`, `api/main.py` request flag, 프론트 ml 배지 컴포넌트 |
| C | git revert 대상 커밋 확정 후 매핑 |

---

## D4 — 가중치 / 정책 변경 권한

### 배경
`pipeline/ranker.DEFAULT_WEIGHTS` 와 `pipeline/policy.SR_LEGAL_FLOOR_*` 의 변경 절차가 문서화돼 있지 않음. CLAUDE.md §11 에는 "분기 검토" 라는 표현만 있음. 누가 언제 어떻게 바꾸나.

### 안건
- `DEFAULT_WEIGHTS` 변경 → 코드 수정 + PR + 회귀 baseline 비교 의무화
- `SR_LEGAL_FLOOR_PCT` (현 20.0) → 법령 변경 시에만. PR 본문에 법령 조항 인용 의무
- entropy 보정 (D1.B 채택 시) → `pipeline/policy.py` 단일 출처. 분기 회의 결정값만 반영
- 8 키워드 (`pipeline/item_keywords.py`) → 운영팀 분기 1회 검토 (CLAUDE.md §11 기준)

### 영향 파일
- `CLAUDE.md` §11 또는 §14 신규 절에 변경 절차 추가 (별도 PR)

---

## 결정 기록 (회의 후 작성)

회의 종료 시점에 표 채워서 commit:

| ID | 채택 옵션 | 사유 (1줄) | 후속 PR 책임자 | 데드라인 |
|---|---|---|---|---|
| D1 | A | entropy 는 보조 KPI 로만, 점수·랭킹 영향 X | YangHyunu | 2026-05-16 |
| D2 | A | CLAUDE.md §13 보류 결정 유지, Phase 3 임베딩과 함께 재논의 | — | — |
| D3 | A | 팀원 ranker 변형은 별도 PR 로 review, 본 브랜치 base 유지 | 팀원 | TBD |
| D4 | 별도 PR | 가중치 변경 절차는 CLAUDE.md 별도 PR 로 후속 처리 | YangHyunu | TBD |

---

## 회의 자료 (선행 준비물)

회의 전에 준비해 두면 좋은 자료:

1. **회귀 baseline 스냅샷** — `tests/fixtures/recommend_v2_baseline.json` 을 `scripts/dump_recommend_baseline.py` 로 생성. 운영 8 키워드 × 대표 예산의 현재 응답.
2. **entropy 분포 측정** (D1) — baseline 위에 후처리 스크립트로 키워드별 entropy 산출.
3. **팀원 브랜치 diff** (D3) — `git diff feat/scoring-mvp-teambase..<teammate-branch> --stat`.
