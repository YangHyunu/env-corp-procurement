# Brooks-Lint Review (3rd run — frontend v2 follow-up)

**Mode:** PR Review
**Scope:** branch `feat/scoring-mvp` vs `main`. 이전 라운드(2회)의 Python 발견 6건은 commit `3ad0928`에서 모두 해소 확인 (SR_LEGAL_FLOOR 단일화 → `pipeline/policy.py`, RuleRanker 권위화 → `scoring.py` 위임, `enrich()` 분해, 단일 connection, 강타입). 이번 라운드는 그 이후 새로 추가된 frontend v2 commit `e391047` (+3,735 / 14 신규 컴포넌트 + hooks) + 표시-계층 무결성에 집중. 건너뜀: `analysis/dashboard_mockup_v2_1.html` (디자인 목업, 비-프로덕션), 이전 라운드 검토 완료된 Python.
**Health Score:** 42/100
**Trend:** 64 → 58 → 42 (−16 from prior run) over last 3 runs

룰베이스 추천 엔진은 정리됐지만, 이번 라운드는 의사결정 표시 계층(Display layer)에서 더 위험한 신호 — 정부 사용자에게 보여주는 "근거" 차트가 `Math.random()`으로 만들어진 가짜이고, 법정 의무비율 판단이 클라이언트에서 재계산되어 서버 결정을 덮어쓴다. 룰 엔진은 정확해도 그 결과를 변형해 노출하는 표시-계약이 Conceptual Integrity를 깬다.

> **Note:** PR > 500 lines는 그 자체가 Change Propagation 신호. frontend 14개 컴포넌트가 한 commit에 묶여 있어 한 번에 보이지 않는 사이즈 — 각 카드/패널/비교/입력을 독립 PR로 쪼갰으면 디자인-시스템 차원의 중복이 더 일찍 보였을 것.

---

## Findings

### 🔴 Critical

**Domain Model Distortion — RadarSection이 `Math.random()`과 조작된 산식으로 가짜 평가점수를 표시**
- **Symptom:** `frontend/src/components/RadarSection.tsx:35` — `value: Math.min(1, Math.max(0, (item.rule_score + Math.random() * 0.1 - 0.05)))`. 매 render마다 `Math.random()`이 호출되어 동일 입력에 매번 다른 차트가 그려진다. Legend(line 41-50)는 `weighted_segments`를 옵셔널 cast로 읽지만 (`item as unknown as { weighted_segments?: ... }`) — 확인 결과 `api/schemas.py:200-217 RecommendationV2Item`에는 `weighted_segments`/`axes` 필드가 **없고**, V1 `RecommendationItem`에만 존재 (line 92-93). `pipeline/recommend_v2.py`의 `_make_recommendation` (line 459-476)도 4축 점수를 emit하지 않으므로 fallback 경로(`item.rule_score * (key === 'sr_diversity' ? 1.2 : key === 'track_record' ? 1.1 : 0.8)`)가 **항상** 실행된다. 결국 4개 축은 단일 `rule_score`에 임의 상수를 곱한 cosmetic transform.
- **Source:** Evans — *Domain-Driven Design*, Domain Model 정확성; Winters et al. — *Software Engineering at Google*, Hyrum's Law (UI가 약속한 "근거" ≠ 코드의 행위)
- **Consequence:** CLAUDE.md §9가 명시한 "calibration 안 된 ML probability를 사용자에게 raw로 노출 금지"의 정신을 한 단계 더 위반한다 — calibration 안 된 점수도 아니고, 의미 없는 난수와 곱셈. 공무원이 "이 업체는 SR 0.85, 가격 0.65, 실적 0.78점이라 추천한다"라고 판단하지만 그 숫자는 매 리렌더 다르고 4축은 한 점수의 변형. 감사 시 "왜 이 업체를 추천했느냐"의 시각적 근거가 거짓으로 드러나면 정부 도구로서 신뢰가 무너진다. 룰 엔진이 정확해도 노출 단계가 거짓이면 의사결정 도구로 쓸 수 없음.
- **Remedy:** (a) backend `pipeline/recommend_v2.py`가 이미 `RuleRanker.score()`에서 4축 weighted_segments를 계산하므로 `_make_recommendation`이 그 dict를 그대로 노출 + `api/schemas.py:200`의 `RecommendationV2Item`에 `axes: dict[str, float]` 추가 + `frontend/src/lib/types.ts:96-113`의 `RecommendationV2Item`에 같은 필드 추가. (b) `Math.random()` 즉시 제거. (c) 단기 임시 조치가 필요하면 RadarSection을 제거하고 `item.reason` 텍스트 + 단일 합계점수 막대로 대체.

**Knowledge Duplication / Hyrum's Law — Compliance를 client에서 재계산해 server 결정을 덮어씀**
- **Symptom:** `frontend/src/App.tsx:104-110` — `compliance: { ...result.compliance, obligation_threshold_pct: srTarget, obligation_met: result.compliance.sr_pct_top_k >= srTarget }`. 서버가 이미 `pipeline/recommend_v2.py:570-572`에서 `SR_LEGAL_FLOOR_PCT` (정확히 20.0, `pipeline/policy.py` 단일 정의) 기준으로 `obligation_met`을 계산해 응답하지만, 클라이언트는 그것을 무시하고 사용자가 Header 설정에서 고른 `srTarget` (15/20/30/40/50%)으로 다시 비교한다. `ComplianceBar.tsx:14`에서 한 번 더 같은 비교 (`met = compliance.sr_pct_top_k >= srTarget`).
- **Source:** Hunt & Thomas — *Pragmatic Programmer*, DRY: Single Source of Truth; Winters et al. — *Software Engineering at Google*, Hyrum's Law; CLAUDE.md §11 obligation 로직 + §12 "공무원 사용자에게 운영 권한 부여 금지"의 정신
- **Consequence:** 사용자가 Header → 설정에서 SR 의무비율 기본값을 15%로 내리고 localStorage에 저장하면, 서버는 같은 응답에 대해 `obligation_met=false` (legal floor 20%)인데 클라이언트는 `obligation_met=true`로 표시. 공무원이 "법정 충족"으로 보고 발주 진행 → 실제로는 미충족. 더 근본 문제: 법정 의무비율은 사용자 토글 대상이 **아니다** (조달사업법 시행령). 클라이언트 localStorage(`eco_sr_target`, `useLocalStorage` line `App.tsx:22`)로 변경 가능하게 만든 것 자체가 사용자가 법령을 우회하는 통로를 코드로 만들어준 것. 서버 로그(미충족)와 화면 표시(충족)가 다르면 감사 추적도 불가능.
- **Remedy:** (a) 서버의 `compliance.obligation_met` + `obligation_threshold_pct`를 single source of truth로 사용 — App.tsx:104-110 클라이언트 재계산 블록 제거, ComplianceBar는 `compliance.obligation_met`을 직접 표시. (b) Header의 SR 의무비율 select는 **표시 정렬용**이거나 제거. 진짜로 30%/40% 강화 정책을 적용하려면 서버 요청 파라미터로 보내고 서버에서 `max(SR_LEGAL_FLOOR_PCT, user_target)` 처리. 어떤 경우에도 "20% 미만"은 클라이언트에서 선택 불가능해야 함. (c) `frontend/src/components/Header.tsx:16` `SR_OPTIONS`에서 `15`를 제거 — 법정 하한 미만은 UI 옵션으로 존재해서는 안 됨.

### 🟡 Warning

**Cognitive Overload / Dependency Disorder — 인라인 스타일 + 명령형 DOM 변이 (`e.currentTarget.style`) 패턴이 6+ 컴포넌트에 반복, Tailwind/shadcn 셋업이 무시됨**
- **Symptom:** `frontend/src/index.css:2-4`에 `@import "tailwindcss"` + `"shadcn/tailwind.css"`가 설정되어 있고 `frontend/src/lib/utils.ts:1-5`에 `cn = twMerge(clsx(...))` 유틸까지 준비됨. 그런데 14개 신규 컴포넌트 어디에도 `className`이 사용되지 않음 — 모두 `style={{ ... }}` 인라인 객체. hover 효과는 `RecommendationCard.tsx:53-66`, `InputForm.tsx:197-208`, `Header.tsx:125-132`, `KpiGrid.tsx:89-96` 등에서 `onMouseEnter={(e) => { e.currentTarget.style.background = '...'; e.currentTarget.style.transform = 'translateY(-1px)'; e.currentTarget.style.boxShadow = '...' }}` 명령형 DOM 변이. RecommendationCard 한 카드의 mouse handler가 4개 속성을 직접 셋팅.
- **Source:** Ousterhout — *A Philosophy of Software Design*, Strategic vs Tactical; Hunt & Thomas — *Pragmatic Programmer*, Orthogonality; Fowler — *Refactoring*, Long Method
- **Consequence:** (a) 컴포넌트 render body가 200~300줄로 비대해 변경 시 인지부하 큼 — InputForm 300줄, Header 285줄, RecommendationCard 217줄 모두 80%가 인라인 style. (b) hover 동작이 stateful — `selected/inCompare` 상태가 mouseLeave 도중 바뀌면 잘못된 boxShadow 복원 (현재 `RecommendationCard.tsx:60-65`는 `if (!selected && !inCompare)` 가드를 두지만 race condition 잠복). (c) 디자인 토큰 (primary `#4f46e5`, hover `#4338ca`, soft `#eef2ff`) — `index.css:14-16`에 이미 CSS variable로 정의되어 있는데 컴포넌트는 hex literal로 반복. 다크모드/리브랜딩 시 grep로 수십 군데 변경 필요. CSS `:hover` 의사클래스 또는 Tailwind `hover:bg-primary` 한 줄로 끝날 코드.
- **Remedy:** (a) hover 핸들러 전부 삭제 + CSS `:hover` (또는 Tailwind `hover:`)로 교체 — 즉시 ~400줄 감소 예상. (b) `--color-primary` 등 이미 정의된 CSS variable을 `var(--color-primary)`로 사용. (c) RecommendationCard / DetailPanel / InputForm 같이 큰 카드는 Tailwind `className="bg-white rounded-xl shadow-sm hover:shadow-md transition"`로 치환. 한 컴포넌트 시범 변환 후 패턴 정착시키기.

**Knowledge Duplication — Tier / SR 뱃지 / 등급 색상 dict가 4개 컴포넌트에 동일 복제**
- **Symptom:** 같은 `{A: '#dcfce7/#15803d', B: '#dbeafe/#1e40af', C: '#f1f5f9/#475569'}` 색상 세트가 `RecommendationCard.tsx:174-178` (TierBadge)와 `DetailPanel.tsx:171-175` (TierTag)에 동일 정의. SR 색상 (`여성기업: #fce7f3/#be185d`, `장애인기업: #fef3c7/#92400e`, `사회적기업: #d1fae5/#065f46`)도 두 곳 (`RecommendationCard.tsx:196-200` BadgeChip + `DetailPanel.tsx:192-196` SrTag)에 똑같이. 위험등급 색상은 `RiskAndStability.tsx:12-17`에 또 다른 4-키 dict (낮음/보통/주의/미확인). `frontend/src/lib/utils.ts:39-46`엔 `badgeKey()` 함수만 있고 색상 정의는 없음.
- **Source:** Hunt & Thomas — *Pragmatic Programmer*, DRY; Fowler — *Refactoring*, Duplicate Code; Brooks — *The Mythical Man-Month*, Conceptual Integrity
- **Consequence:** "B등급 색상을 더 진하게" 같은 변경이 두 군데 동시 수정 필요. SR 뱃지 한 종류 추가 (예: 자활기업, CLAUDE.md §1이 명시한 분류) 시 두 dict literal에 키 추가 누락하면 카드에서는 정의된 색, 디테일 패널에서는 디폴트 보라색이 나오는 시각적 불일치 — 같은 업체가 화면 두 곳에서 다른 색으로 표시. RecommendationCard와 DetailPanel은 같은 BRN의 같은 뱃지를 동시에 보여주는 위치라 시각적 일관성이 더 중요.
- **Remedy:** `frontend/src/lib/badges.ts` 한 모듈에 `TIER_COLORS`, `SR_BADGE_COLORS`, `RISK_GRADE_COLORS` 상수 정의 + `<TierBadge tier={...}/>` 공용 컴포넌트로 추출. 컴포넌트 5개에서 import 한 줄로 끝. 더 발전형: Tailwind 토큰 (`bg-tier-a`, `text-tier-a`) + `tailwind.config`에 색상 등록.

**Cognitive Overload — `Dashboard()` (App.tsx) 245줄에 6 useState + 3 useEffect + 파생 상태 + 3-column grid JSX 혼재**
- **Symptom:** `frontend/src/App.tsx:20-246` 한 함수에 (i) settings localStorage hooks 3개 (line 22-24), (ii) 입력 상태 3개 (selectedKeyword/srFilter/budget, line 35-41), (iii) 결과 상태 3개 (selectedBrn/compareMode/compareSet, line 44-46), (iv) `useKeywords`/`useRecommend` (line 49-50), (v) auto-select effects 2개 (line 53-65 + 79-83), (vi) handleSubmit/handleToggleCompare/budgetMillion/compliance 파생 (line 67-113), (vii) 3-column grid JSX (line 115-244). 50줄 가이드의 5배.
- **Source:** Fowler — *Refactoring*, Long Method; McConnell — *Code Complete*, Ch. 7; Ousterhout — *A Philosophy of Software Design*, Shallow Module
- **Consequence:** 새 입력 필드 한 개 추가 (예: 향후 "지역 필터") = 같은 함수 안에서 useState + handler + JSX + 자동 추천 effect deps + InputForm props 모두 동시 수정. compareMode와 selectedBrn의 상호배제 로직이 JSX 안에 ternary로 녹아있어 (line 219-242) 변경 시 회귀 위험. 단위 테스트 작성 사실상 불가 — 모든 hook을 mocking. CLAUDE.md §11이 v2.1, v2.2, v3로 카드 항목/필터를 늘려갈 계획이라 이 함수는 빠르게 더 길어질 궤적.
- **Remedy:** (a) `useDashboardState()` custom hook으로 6 useState + 3 effect를 추출 → Dashboard는 view + wiring만. (b) `<RightColumn>` 컴포넌트로 `compareMode ? <CompareTable> : <DetailPanel>` 분기를 격리. (c) `<MainColumn>`로 추천 결과 영역 분리. Dashboard 본문이 ~50줄까지 축소 가능.

**Hyrum's Law — ComplianceBar의 "상위 K" 표시가 top_k 설정과 무관하게 항상 5**
- **Symptom:** `frontend/src/components/ComplianceBar.tsx:74` — `상위 ${compliance.sr_in_top_k + (5 - srInK > 0 ? (5 - srInK) : 0)}개`. 산식을 풀면 `srInK ≤ 5`인 모든 경우에 결과가 정확히 5 (예: srInK=2 → 2+3=5, srInK=0 → 0+5=5, srInK=5 → 5+0=5). `Header.tsx:17`의 `TOPK_OPTIONS = [3, 5, 10]`을 사용자가 3 또는 10으로 바꿔도 항상 "상위 5"로 표시.
- **Source:** Winters et al. — *Software Engineering at Google*, Hyrum's Law; McConnell — *Code Complete*, Magic Numbers; Fowler — *Refactoring*, 의도가 가려진 산식
- **Consequence:** 사용자가 top_k=3로 좁히면 카드는 3개인데 ComplianceBar는 "상위 5개 중 정책 인증 N개"라고 거짓 표시 → 즉시 신뢰 의심. top_k=10이면 "상위 5"로 표시 + srInK가 6 이상이면 srInK 그대로 표시 (분기점이 의미 없는 곳에 위치). 답이 명확한 값(`recs.length` 또는 `topK` prop)을 obscure 산식으로 계산.
- **Remedy:** `top_k` (또는 `result.recommendations.length`)를 prop으로 받아 그대로 표시: `상위 ${topK}개 후보 중 정책 인증 기업 ${srInK}개`. 현재 산식 삭제. App.tsx에서 `<ComplianceBar topK={topK} ... />`로 전달.

**Hyrum's Law — InputForm 카피가 "조건 변경 시 자동 반영"이라 약속하지만 실제로는 키워드 변경만 자동 반영**
- **Symptom:** `frontend/src/components/InputForm.tsx:60-62` — 패널 상단에 `조건 변경 시 자동 반영` 카피. 그러나 `App.tsx:60-65` 자동 추천 useEffect의 deps가 `[selectedKeyword]`뿐. srFilter 토글이나 budget 변경은 사용자가 수동으로 line 211 `추천 재산출` 버튼을 눌러야 fetch.
- **Source:** Winters et al. — Hyrum's Law (UI 카피 ≠ 행위); Evans — *Domain-Driven Design*, Ubiquitous Language
- **Consequence:** 사용자가 "사회적기업" 체크 → 결과 카드가 그대로 → "버그?" 또는 (더 위험) "필터가 적용된 줄 알고" 이전 결과 기준으로 발주 결정. `liveCount`도 server에서 받은 KPI라 필터 토글에도 즉시 변하지 않으므로 이중으로 혼란. CLAUDE.md §11 "정책 필터 0~3개 — hard filter"라는 도메인 약속과 UI의 "자동 반영" 약속 둘 다 깨짐.
- **Remedy:** 둘 중 하나 — (a) UI 카피를 정확하게: "변경 후 '추천 재산출'을 눌러주세요" (1줄 수정으로 끝). (b) effect deps 확장 + budget은 debounce: `useEffect(() => { handleSubmit() }, [selectedKeyword, srFilter])` + budget은 `useDebouncedValue(budget, 500)` 별도 effect. (a)가 가장 안전한 단기 해결.

### 🟢 Suggestion

**Knowledge Duplication — `Settings` (App.tsx) vs `SettingsState` (Header.tsx) 같은 모양의 인터페이스 두 번**
- **Symptom:** `App.tsx:14-18`의 `interface Settings`와 `Header.tsx:5-9`의 `interface SettingsState`가 동일한 3-필드 (`sr_target: number`, `top_k: number`, `budget_unit: string`). `frontend/src/lib/types.ts`에 다른 도메인 타입은 모두 모여있는데 이 둘만 컴포넌트 파일 내부에 흩어져 있음.
- **Source:** Hunt & Thomas — DRY; Evans — Ubiquitous Language
- **Consequence:** 옵셔널 필드 추가 (예: `theme?: 'light' | 'dark'`) 시 두 곳 동시 수정. TypeScript가 mismatch를 catch해주긴 하지만, 같은 도메인 개념이 두 이름으로 존재하는 자체가 신규 contributor를 혼란시킨다.
- **Remedy:** `frontend/src/lib/types.ts`에 `export interface DashboardSettings { sr_target: number; top_k: number; budget_unit: string }` 한 번 정의 후 두 컴포넌트가 import.

**Knowledge Duplication — `SR_OPTIONS = [15, 20, 30, 40, 50]`가 Header.tsx와 ComplianceBar.tsx에 동일 하드코딩**
- **Symptom:** `Header.tsx:16` + `ComplianceBar.tsx:9` 동일 const. 게다가 (Critical #2 참조) 15는 법정 하한(20%) 미만으로 옵션 자체가 부적절.
- **Source:** Hunt & Thomas — DRY; CLAUDE.md §11 + `pipeline/policy.py` (SR_LEGAL_FLOOR_PCT 단일 정의의 정신)
- **Consequence:** 옵션 추가/삭제 시 두 곳 비대칭 위험. 또한 Python 쪽은 `SR_LEGAL_FLOOR_PCT` 단일 상수로 정리됐는데 frontend에는 같은 도메인 상수가 hardcoded duplicate.
- **Remedy:** `frontend/src/lib/constants.ts`에 `export const SR_LEGAL_FLOOR_PCT = 20` + `export const SR_TARGET_OPTIONS = [SR_LEGAL_FLOOR_PCT, 30, 40, 50] as const` (15 제거). 코멘트로 "법정 하한 미만 옵션은 UI에 노출 금지 — pipeline/policy.py 와 동기화" 명시.

**Coverage Illusion — frontend 14개 신규 컴포넌트 + 3개 hooks + utils — 0 tests**
- **Symptom:** `find frontend -name "*.test.*"` 0건. `tests/` 디렉토리는 Python 전용 (`test_recommend_v2_pure.py` 1개). 가장 비결정적인 코드 (RadarSection의 `Math.random`, ComplianceBar의 5-고정 산식, App.tsx의 effect deps)도 검증 없음.
- **Source:** Feathers — *Working Effectively with Legacy Code*, Ch. 1: 테스트 없는 코드 = legacy
- **Consequence:** Critical #1 (Math.random)도 Critical #2 (compliance override)도 단순 unit/render test로 catch될 수 있는 회귀가 production까지 흘러들 위험. 이전 라운드에 지적된 Python `tests/test_recommend_v2_pure.py`는 작성됐지만 frontend는 같은 약속 없음.
- **Remedy:** `vitest` + `@testing-library/react` 도입. 우선순위: (i) `RadarSection`의 결정성 (`Math.random` 제거 후 동일 입력 → 동일 출력 단언), (ii) `ComplianceBar` 표시 산식 (`topK`별 "상위 N" 표시 검증), (iii) `App.tsx`의 자동 추천 effect (selectedKeyword 변경에만 반응 / 다른 입력엔 미반응을 명시 검증).

---

**Recommended fix order:** (1) RadarSection `Math.random` 제거 + backend `axes` 노출 — 정부 도구로서 신뢰의 마지노선; (2) compliance 클라이언트 재계산 제거 + 15% 옵션 제거 — 법령 우회 통로 닫기; (3) ComplianceBar "상위 K" 산식 수정 + InputForm 카피 정정 — UI 거짓말 두 개 정리, 1줄씩이라 묶어서; (4) Tier/SR 색상 dict 단일화 + `lib/badges.ts` 추출; (5) hover handler 일괄 CSS화 → Dashboard 분해 (대형 리팩토링); (6) frontend 테스트 도입.

## Summary

가장 시급한 건 표시 계층의 두 거짓말 — `Math.random()`으로 만든 가짜 평가차트와, server의 법정 의무비율 판단을 client localStorage 토글로 덮어쓰는 compliance 재계산이다. 룰 엔진은 이전 라운드에서 잘 정리됐지만, 그 결과를 정부 사용자에게 노출하는 컴포넌트가 도메인 무결성을 일관되게 깨고 있어 의사결정 도구로서의 신뢰가 무너진다. 부수적으로 인라인 스타일 + 명령형 DOM 변이 패턴이 14개 컴포넌트에 자리잡았는데, 프로젝트가 이미 Tailwind/shadcn 셋업을 가지고도 사용하지 않는 상태 — 한 컴포넌트 시범 전환으로 패턴 정착이 빠를 것.
