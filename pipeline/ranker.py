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

        # -------------------------------------------------
        # 필수 컬럼 방어
        # -------------------------------------------------
        required_cols = [
            "award_count",
            "sr_count",
            "avg_bid_rate",
            "award_total_amt",
        ]

        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"missing required columns: {missing_cols}")

        # -------------------------------------------------
        # 결측 / 타입 정리
        # -------------------------------------------------
        df["award_count"] = pd.to_numeric(df["award_count"], errors="coerce").fillna(0)
        df["sr_count"] = pd.to_numeric(df["sr_count"], errors="coerce").fillna(0)
        df["avg_bid_rate"] = pd.to_numeric(df["avg_bid_rate"], errors="coerce")
        df["award_total_amt"] = pd.to_numeric(df["award_total_amt"], errors="coerce").fillna(0)

        # -------------------------------------------------
        # Axis 1: supply_stability
        # pool 내 award_count 백분위
        # -------------------------------------------------
        df["rank_award_count"] = df["award_count"].rank(
            method="min",
            ascending=False,
        )

        df["axis_supply_stability"] = (
            n - df["rank_award_count"] + 1
        ) / n

        df.loc[df["award_count"] == 0, "axis_supply_stability"] = 0.0

        # -------------------------------------------------
        # Axis 2: sr_diversity
        # 기존: sr_count 개수에 따라 0~1 점수
        # 변경: 사회적 인증이 하나라도 있으면 1.0, 없으면 0.0
        # -------------------------------------------------
        df["axis_sr_diversity"] = (
            df["sr_count"].astype(float) > 0
        ).astype(float)

        # -------------------------------------------------
        # Axis 3: track_record
        # 낙찰 건수 + 평균 투찰률 기반 실적 점수
        # -------------------------------------------------
        max_count = max(int(df["award_count"].max() or 1), 1)

        norm_count = df["award_count"].astype(float) / max_count
        norm_bid_rate = df["avg_bid_rate"].fillna(0.0).astype(float) / 100.0

        # avg_bid_rate가 없는 업체는 bid_rate 점수 반영하지 않음
        rate_weight = df["avg_bid_rate"].notna().astype(float)

        df["axis_track_record"] = (
            0.6 * norm_count
            + 0.4 * norm_bid_rate * rate_weight
        ).clip(0.0, 1.0)

        # -------------------------------------------------
        # Axis 4: price_competitiveness
        # 단가 = award_total_amt / award_count
        # 단가가 낮을수록 높은 점수
        # -------------------------------------------------
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

        # -------------------------------------------------
        # 4축 가중합
        # -------------------------------------------------
        w = self.weights

        df["composite_score"] = (
            w["supply_stability"]        * df["axis_supply_stability"]
            + w["sr_diversity"]         * df["axis_sr_diversity"]
            + w["track_record"]         * df["axis_track_record"]
            + w["price_competitiveness"] * df["axis_price_competitiveness"]
        )

        # -------------------------------------------------
        # SR soft floor
        # 사회적 인증 보유 업체가 3개 이상 있을 때,
        # sr_count = 0 업체는 후순위로 demote
        # -------------------------------------------------
        n_sr_cert = int((df["sr_count"] > 0).sum())

        df["is_sr_demoted"] = False

        if n_sr_cert >= 3:
            demote_mask = df["sr_count"] == 0

            df.loc[demote_mask, "composite_score"] -= 1.0
            df.loc[demote_mask, "is_sr_demoted"] = True

        # -------------------------------------------------
        # 결과 반환
        # -------------------------------------------------
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
