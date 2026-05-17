from __future__ import annotations

from typing import Any, Protocol

import numpy as np
import pandas as pd


DEFAULT_WEIGHTS: dict[str, float] = {
    "track_record":          0.33,
    "price_competitiveness": 0.34,
    "supply_stability":      0.33,
}


class Ranker(Protocol):
    """Stage 2 ranker 인터페이스 — RuleRanker / 향후 LGBMRanker 둘 다 구현."""

    def score(
        self,
        candidates: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """후보별 점수 매김. 입력 dict 에 score / axes 추가해 반환."""
        ...


def _validate_weights(weights: dict[str, float]) -> None:
    s = sum(weights.values())
    if abs(s - 1.0) > 1e-3:
        raise ValueError(f"weights must sum to 1.0 (got {s:.4f})")


class RuleRanker:
    """3축 가중합 — 실적/가격/공급안정 (SR 은 토글 필터로 분리)."""

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

        # 필수 컬럼 방어
        required_cols = [
            "award_count",
            "avg_bid_rate",
            "award_total_amt",
        ]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"missing required columns: {missing_cols}")

        # 결측 / 타입 정리
        df["award_count"] = pd.to_numeric(df["award_count"], errors="coerce").fillna(0)
        df["avg_bid_rate"] = pd.to_numeric(df["avg_bid_rate"], errors="coerce")
        df["award_total_amt"] = pd.to_numeric(df["award_total_amt"], errors="coerce").fillna(0)

        # Axis 1: supply_stability — pool 내 award_count 백분위
        df["rank_award_count"] = df["award_count"].rank(
            method="min",
            ascending=False,
        )
        df["axis_supply_stability"] = (
            n - df["rank_award_count"] + 1
        ) / n
        df.loc[df["award_count"] == 0, "axis_supply_stability"] = 0.0

        # Axis 2: track_record — 낙찰 건수 + 평균 투찰률 기반 실적 점수
        max_count = max(int(df["award_count"].max() or 1), 1)
        norm_count = df["award_count"].astype(float) / max_count
        norm_bid_rate = df["avg_bid_rate"].fillna(0.0).astype(float) / 100.0
        rate_weight = df["avg_bid_rate"].notna().astype(float)
        df["axis_track_record"] = (
            0.6 * norm_count
            + 0.4 * norm_bid_rate * rate_weight
        ).clip(0.0, 1.0)

        # Axis 3: price_competitiveness — 단가 낮을수록 높은 점수
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

        # 3축 가중합
        w = self.weights
        df["composite_score"] = (
            w["supply_stability"]        * df["axis_supply_stability"]
            + w["track_record"]          * df["axis_track_record"]
            + w["price_competitiveness"] * df["axis_price_competitiveness"]
        )

        out: list[dict[str, Any]] = []
        for cand, (_, row) in zip(candidates, df.iterrows()):
            out.append({
                **cand,
                "rule_score": float(max(row["composite_score"], 0.0)),
                "axes": {
                    "supply_stability":      float(row["axis_supply_stability"]),
                    "track_record":          float(row["axis_track_record"]),
                    "price_competitiveness": float(row["axis_price_competitiveness"]),
                },
                "is_sr_demoted": False,
            })
        return out
