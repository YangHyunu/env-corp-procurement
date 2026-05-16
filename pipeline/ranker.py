"""
Ranker Protocol + 구현체 — Stage 2 (Rank) swap point.

(A) RuleRanker — 4축 가중합 (현재)
(B) LGBMRanker — synthetic bid 기반 LGBM (향후, 미구현)

candidates 는 dict list. 필수 키:
  brn, sr_count, female_ceo_flag, disabled_corp_flag, social_corp_flag,
  award_count, award_total_amt, avg_bid_rate

회의 결정 영향 (docs/decisions/2026-05-16_team_integration_meeting.md):
  - D1.A (entropy = 보조 KPI) → 본 모듈에 `compute_pool_entropy` 함수만 추가
  - D1.B (entropy = 가중치 보정) → `RuleRanker.__init__` 시그니처 변경 + 가중치 동적 조정
  - D3.B (LGBMRanker swap) → 신규 `LGBMRanker` 클래스 추가, `Ranker` Protocol 그대로 구현
"""
from __future__ import annotations

from typing import Any, Protocol

import numpy as np
import pandas as pd

from pipeline.policy import SR_LEGAL_FLOOR_FRACTION


DEFAULT_WEIGHTS: dict[str, float] = {
    "sr_diversity":          0.35,
    "track_record":          0.30,
    "price_competitiveness": 0.20,
    "supply_stability":      0.15,
}


class Ranker(Protocol):
    """Stage 2 ranker 인터페이스 — RuleRanker / 향후 LGBMRanker 둘 다 구현."""
    def score(
        self,
        candidates: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """후보별 점수 매김. 입력 dict 에 score / axes / is_sr_demoted 추가해 반환."""
        ...


def _validate_weights(weights: dict[str, float]) -> None:
    s = sum(weights.values())
    if abs(s - 1.0) > 1e-3:
        raise ValueError(f"weights must sum to 1.0 (got {s:.4f})")
    if weights.get("sr_diversity", 0.0) < SR_LEGAL_FLOOR_FRACTION - 1e-3:
        raise ValueError(
            f"sr_diversity weight must be ≥ {SR_LEGAL_FLOOR_FRACTION} (legal floor)"
        )


class RuleRanker:
    """4축 가중합 — pipeline.scoring 의 v1 로직 이식."""

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = weights or DEFAULT_WEIGHTS
        _validate_weights(self.weights)

    def score(
        self,
        candidates: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []

        df = pd.DataFrame(candidates).copy()
        n = len(df)

        # Axis 1: supply_stability — pool 내 award_count 백분위
        df["rank_award_count"] = df["award_count"].rank(method="min", ascending=False)
        df["axis_supply_stability"] = (n - df["rank_award_count"] + 1) / n
        df.loc[df["award_count"] == 0, "axis_supply_stability"] = 0.0

        # Axis 2: sr_diversity — 0~3 인증 수 / 3
        df["axis_sr_diversity"] = df["sr_count"].clip(0, 3).astype(float) / 3.0

        # Axis 3: track_record — count + bid_rate 가중합
        max_count = max(int(df["award_count"].max() or 1), 1)
        norm_count = df["award_count"].astype(float) / max_count
        norm_bid_rate = df["avg_bid_rate"].fillna(0.0).astype(float) / 100.0
        rate_weight = df["avg_bid_rate"].notna().astype(float)
        df["axis_track_record"] = (
            0.6 * norm_count + 0.4 * norm_bid_rate * rate_weight
        ).clip(0.0, 1.0)

        # Axis 4: price_competitiveness — 단가(award_total_amt / count) 역백분위
        unit_price = (
            df["award_total_amt"].astype(float)
            / df["award_count"].replace(0, np.nan)
        )
        if unit_price.notna().sum() >= 3:
            df["axis_price_competitiveness"] = (
                1.0 - unit_price.rank(method="min", pct=True)
            ).fillna(0.5)
        else:
            df["axis_price_competitiveness"] = 0.5

        # 가중합
        w = self.weights
        df["composite_score"] = (
            w["supply_stability"]      * df["axis_supply_stability"]
            + w["sr_diversity"]        * df["axis_sr_diversity"]
            + w["track_record"]        * df["axis_track_record"]
            + w["price_competitiveness"] * df["axis_price_competitiveness"]
        )

        # SR soft floor — n_sr_certified ≥ 3 일 때 sr_count=0 demote
        n_sr_cert = int((df["sr_count"] > 0).sum())
        df["is_sr_demoted"] = False
        if n_sr_cert >= 3:
            demote_mask = df["sr_count"] == 0
            df.loc[demote_mask, "composite_score"] -= 1.0
            df.loc[demote_mask, "is_sr_demoted"] = True

        # 결과를 candidates 에 머지해 반환
        out: list[dict[str, Any]] = []
        for cand, (_, row) in zip(candidates, df.iterrows()):
            out.append({
                **cand,
                "rule_score": float(max(row["composite_score"], 0.0)),
                "axes": {
                    "supply_stability":      float(row["axis_supply_stability"]),
                    "sr_diversity":          float(row["axis_sr_diversity"]),
                    "track_record":          float(row["axis_track_record"]),
                    "price_competitiveness": float(row["axis_price_competitiveness"]),
                },
                "is_sr_demoted": bool(row["is_sr_demoted"]),
            })
        return out


# ── 보조 KPI: 후보 풀 분산도 (D1 옵션 A) ────────────────────────────
_ENTROPY_AXES: tuple[str, ...] = (
    "supply_stability",
    "sr_diversity",
    "track_record",
    "price_competitiveness",
)


def compute_pool_entropy(candidates: list[dict[str, Any]]) -> float | None:
    """후보 풀의 4축 점수 결합 분포 Shannon entropy (0~1 정규화).

    D1 옵션 A — 점수·랭킹·tier 에 절대 영향 X. 순수 분석 함수.

    동작:
      - 후보 < 2 → None (의미 없음)
      - 분산 0 축은 자동 skip (uniform 축은 entropy 기여 X)
      - 결합 분포 = 4축 점수 행렬(n × k)을 평탄화해 단일 확률 분포로 정규화
      - max_entropy = log(n × k) 로 정규화 (0~1)
      - 모든 축이 분산 0 또는 합 0 이면 None (degenerate pool)

    Args:
      candidates: `RuleRanker.score()` 결과 dict 리스트 (`axes` 키 포함).

    Returns:
      0.0 ~ 1.0 float, 또는 None (계산 불가).
    """
    if not candidates or len(candidates) < 2:
        return None

    # 4축 행렬 추출 (shape: n × len(axes_used))
    axis_cols: list[np.ndarray] = []
    for axis_name in _ENTROPY_AXES:
        col = np.array(
            [float(c.get("axes", {}).get(axis_name, 0.0)) for c in candidates],
            dtype=float,
        )
        # 분산 0 축은 skip — entropy 기여 X
        if col.std() > 1e-9:
            axis_cols.append(col)

    if not axis_cols:
        return None

    matrix = np.column_stack(axis_cols)  # shape (n, k)
    n = matrix.shape[0]
    k = matrix.shape[1]

    # 결합 분포: matrix 전체를 평탄화해 단일 확률 분포로 정규화.
    # 이 방식은 (i) 축 간 점수 차이 + (ii) 후보 간 점수 차이를 모두 반영한다.
    # 모든 셀이 동일 값이면 max entropy (= log(n*k)) → 정규화값 1.0
    # 모든 mass 가 한 셀에 몰리면 entropy 0 → 정규화값 0.0
    flat = matrix.flatten().astype(float)
    total = flat.sum()
    if total <= 0:
        return None
    probs = flat / total
    probs = probs[probs > 1e-12]
    if probs.size < 2:
        return None

    # Shannon entropy (자연 로그)
    entropy_val = float(-np.sum(probs * np.log(probs)))
    # 정규화: max = log(n × k) — 모든 셀 uniform 일 때의 entropy
    max_entropy = float(np.log(n * k))
    if max_entropy <= 0:
        return None

    return round(min(max(entropy_val / max_entropy, 0.0), 1.0), 4)
