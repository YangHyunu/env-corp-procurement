"""
recommend_v2 회귀 baseline 스냅샷 생성.

운영 키워드 × 대표 예산 N 케이스의 현재 `recommend()` 응답을 JSON 으로 저장한다.
통합 PR(D1.B / D3.B / D3.C 등 점수에 영향 가는 변경) 에서 사용해 점수·랭킹·tier
회귀를 검출한다.

DB 연결 필요 — `DATABASE_URL` 환경변수 또는 default `postgresql:///eco`.

실행:
  uv run python scripts/dump_recommend_baseline.py

출력:
  tests/fixtures/recommend_v2_baseline.json
"""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from pipeline.recommend_v2 import RecommendV2Request, recommend


FIXTURE_PATH = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "recommend_v2_baseline.json"

# 키워드 × 대표 예산 — 분포 다양성을 위해 키워드별로 1 케이스
CASES: list[tuple[str, int]] = [
    ("하수처리용 펌프",   800),   # 풀 두꺼움, 표준 케이스
    ("슬러지 탈수기",     1200),  # 중간 규모
    ("소각로 내화벽돌",   500),   # 데이터 한계 (n=2~3)
    ("바이오가스 발전기", 2000),  # 대형
    ("수질측정센서",      300),   # 소형
    ("대기오염 측정장비", 600),
    ("폐수처리약품",      400),
    ("활성탄 필터",       250),
]

SR_FILTER_NO = {"social_corp": False, "female_ceo": False, "disabled_corp": False}

# 카드별 필드 중 회귀 검증에 의미 있는 부분만 추림 (시간 의존 필드 제외).
# data_cutoff, last_synced_at 같은 운영 메타는 매 실행마다 바뀌어 회귀 노이즈가 됨.
RECOMMENDATION_KEYS = (
    "rank", "brn", "corp_name", "tier", "badges",
    "rule_score", "axes", "ml_score", "score_used",
)


def _serialize(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    if hasattr(obj, "model_dump"):  # Pydantic v2
        return obj.model_dump()
    if hasattr(obj, "dict"):        # Pydantic v1
        return obj.dict()
    return obj


def _snapshot_recommendation(item: Any) -> dict:
    full = _serialize(item)
    return {k: full.get(k) for k in RECOMMENDATION_KEYS}


def _snapshot_response(resp: Any) -> dict:
    data = _serialize(resp)
    kpi = data.get("kpi") or {}
    compliance = data.get("compliance") or {}
    return {
        "item_keyword": data.get("item_keyword"),
        "matched_prefix4": data.get("matched_prefix4"),
        "kpi": {
            "pool_size": kpi.get("pool_size"),
            "sr_count": kpi.get("sr_count"),
            "sr_pct": kpi.get("sr_pct"),
            "supply_risk": kpi.get("supply_risk"),
            "contract_recommend": kpi.get("contract_recommend"),
        },
        "compliance": {
            "sr_in_top_k": compliance.get("sr_in_top_k"),
            "sr_pct_top_k": compliance.get("sr_pct_top_k"),
            "obligation_met": compliance.get("obligation_met"),
        },
        "recommendations": [
            _snapshot_recommendation(r) for r in data.get("recommendations") or []
        ],
    }


def main() -> None:
    baseline: dict[str, dict] = {}
    for keyword, budget_million in CASES:
        req = RecommendV2Request(
            item_keyword=keyword,
            budget_million_won=budget_million,
            sr_filter=SR_FILTER_NO,
            top_k=5,
        )
        resp = recommend(req)
        key = f"{keyword}__{budget_million}M"
        baseline[key] = _snapshot_response(resp)
        print(f"[ok] {key}  pool={baseline[key]['kpi']['pool_size']}  n_rec={len(baseline[key]['recommendations'])}")

    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"\nwrote {FIXTURE_PATH} ({FIXTURE_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
