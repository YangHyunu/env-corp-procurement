"""Pure-logic tests for pipeline.ranker — no DB, no network.

Run:
  uv run python -m unittest tests.test_ranker -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.cluster_groups import (  # noqa: E402
    AUTO_SR,
    DORMANT,
    NOISE,
    REAL_SR,
    VETERAN,
    label_to_group,
)
from pipeline.policy import SR_LEGAL_FLOOR_FRACTION  # noqa: E402
from pipeline.ranker import (  # noqa: E402
    DEFAULT_WEIGHTS,
    RuleRanker,
    _apply_cluster_adjustment,
    _cluster_weight_delta,
)
from pipeline.recommend_v2 import _load_knn_lookup  # noqa: E402


# ──────────────────────────────────────────────────────────────────
# US-002 — SR floor 재정규화 후 보장
# ──────────────────────────────────────────────────────────────────
class TestApplyClusterAdjustment(unittest.TestCase):
    def test_none_group_returns_default(self):
        """group=None → base_weights (SR 하한 이미 충족)."""
        out = _apply_cluster_adjustment(DEFAULT_WEIGHTS, None)
        self.assertEqual(out, DEFAULT_WEIGHTS)
        self.assertAlmostEqual(sum(out.values()), 1.0, places=6)

    def test_dormant_preserves_sr_floor(self):
        """dormant 보정 (sr -0.05) 후에도 SR ≥ legal floor, 합=1.0."""
        out = _apply_cluster_adjustment(DEFAULT_WEIGHTS, DORMANT)
        self.assertGreaterEqual(out["sr_diversity"], SR_LEGAL_FLOOR_FRACTION - 1e-9)
        self.assertAlmostEqual(sum(out.values()), 1.0, places=6)

    def test_real_sr_increases_sr(self):
        """real_sr 보정 (sr +0.10, price -0.10) → sr ↑, 합=1.0."""
        out = _apply_cluster_adjustment(DEFAULT_WEIGHTS, REAL_SR)
        self.assertGreater(out["sr_diversity"], DEFAULT_WEIGHTS["sr_diversity"])
        self.assertAlmostEqual(sum(out.values()), 1.0, places=6)

    def test_veteran_increases_supply(self):
        out = _apply_cluster_adjustment(DEFAULT_WEIGHTS, VETERAN)
        self.assertGreater(out["supply_stability"], DEFAULT_WEIGHTS["supply_stability"])
        self.assertAlmostEqual(sum(out.values()), 1.0, places=6)
        # SR 하한도 유지
        self.assertGreaterEqual(out["sr_diversity"], SR_LEGAL_FLOOR_FRACTION - 1e-9)

    def test_auto_sr_no_change(self):
        out = _apply_cluster_adjustment(DEFAULT_WEIGHTS, AUTO_SR)
        for k in DEFAULT_WEIGHTS:
            self.assertAlmostEqual(out[k], DEFAULT_WEIGHTS[k], places=6)

    def test_floor_enforced_with_aggressive_base(self):
        """매우 낮은 sr base (0.05) + dormant 보정 → SR floor 보장."""
        base = {
            "sr_diversity": 0.05,
            "track_record": 0.30,
            "price_competitiveness": 0.50,
            "supply_stability": 0.15,
        }
        out = _apply_cluster_adjustment(base, DORMANT)
        self.assertGreaterEqual(out["sr_diversity"], SR_LEGAL_FLOOR_FRACTION - 1e-9)
        self.assertAlmostEqual(sum(out.values()), 1.0, places=6)

    def test_noise_treated_like_dormant(self):
        out_noise = _apply_cluster_adjustment(DEFAULT_WEIGHTS, NOISE)
        out_dorm = _apply_cluster_adjustment(DEFAULT_WEIGHTS, DORMANT)
        for k in DEFAULT_WEIGHTS:
            self.assertAlmostEqual(out_noise[k], out_dorm[k], places=6)


class TestClusterWeightDelta(unittest.TestCase):
    def test_none_zero_delta(self):
        self.assertEqual(
            _cluster_weight_delta(None),
            {"sr_diversity": 0.0, "track_record": 0.0,
             "price_competitiveness": 0.0, "supply_stability": 0.0},
        )

    def test_unknown_group_zero_delta(self):
        self.assertEqual(
            _cluster_weight_delta("unknown_group_xyz"),
            {"sr_diversity": 0.0, "track_record": 0.0,
             "price_competitiveness": 0.0, "supply_stability": 0.0},
        )


# ──────────────────────────────────────────────────────────────────
# US-001 — label_to_group
# ──────────────────────────────────────────────────────────────────
class TestLabelToGroup(unittest.TestCase):
    def test_veteran(self):
        self.assertEqual(
            label_to_group("환경공단 주력 공급사 — 펌프 제조사 (한 곳당 평균 7.9억 누적)"),
            VETERAN,
        )

    def test_real_sr_priority_over_social(self):
        # '장애인·사회적기업' 가 '사회적기업' 보다 먼저 매칭
        self.assertEqual(
            label_to_group("장애인·사회적기업 100% — 펌프 제조사"),
            REAL_SR,
        )

    def test_auto_sr(self):
        self.assertEqual(
            label_to_group("여성 대표 자동등록 SR (실제 인증 3%만 보유) — 계측 장비 등록사"),
            AUTO_SR,
        )

    def test_dormant(self):
        self.assertEqual(
            label_to_group("최근 27개월 무낙찰 — 산업용 가스 유통사 (등록 11년차)"),
            DORMANT,
        )

    def test_noise(self):
        self.assertEqual(
            label_to_group("분류외 (어느 군집에도 안 묶임)"),
            NOISE,
        )

    def test_none_for_empty(self):
        self.assertIsNone(label_to_group(None))
        self.assertIsNone(label_to_group(""))

    def test_none_for_unrecognized(self):
        self.assertIsNone(label_to_group("이상한 라벨 — 매핑 불가"))


# ──────────────────────────────────────────────────────────────────
# US-003 — KNN sim 빈 값 / 0 row skip
# ──────────────────────────────────────────────────────────────────
class TestKnnLookup(unittest.TestCase):
    def setUp(self):
        # lru_cache 우회 — 매 테스트마다 mock CSV 강제 로드
        import pipeline.recommend_v2 as rv2
        self.rv2 = rv2
        self._orig_path = rv2.KNN_CANDIDATES_PATH
        _load_knn_lookup.cache_clear()

    def tearDown(self):
        self.rv2.KNN_CANDIDATES_PATH = self._orig_path
        _load_knn_lookup.cache_clear()

    def test_skips_zero_sim_and_empty(self):
        import tempfile
        csv_content = (
            "brn,nearest_ref_brn,nearest_ref_name,similarity\n"
            "1111111111,9999999999,참조사,0.85\n"
            "2222222222,8888888888,영점사,0.0\n"          # skip — sim=0
            "3333333333,7777777777,빈값사,\n"             # skip — sim 빈값
            "4444444444,6666666666,음수사,-0.5\n"         # skip — sim<0
            "5555555555,5555555555,깨진사,abc\n"          # skip — parse 실패
            "6666666666,4444444444,통과사,0.42\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8-sig",
        ) as f:
            f.write(csv_content)
            tmp_path = Path(f.name)
        try:
            self.rv2.KNN_CANDIDATES_PATH = tmp_path
            _load_knn_lookup.cache_clear()
            out = _load_knn_lookup()
            self.assertIn("1111111111", out)
            self.assertNotIn("2222222222", out)  # sim=0
            self.assertNotIn("3333333333", out)  # empty
            self.assertNotIn("4444444444", out)  # negative
            self.assertNotIn("5555555555", out)  # parse fail
            self.assertIn("6666666666", out)
            self.assertEqual(out["1111111111"]["similarity"], 0.85)
        finally:
            tmp_path.unlink(missing_ok=True)


# ──────────────────────────────────────────────────────────────────
# US-005 — vectorize: 결과 동등성 확인
# ──────────────────────────────────────────────────────────────────
def _sample_candidates() -> list[dict]:
    """5 BRN 표준 후보 — 가중치 보정 분기 다양화."""
    return [
        {"brn": "A", "sr_count": 3, "award_count": 10,
         "award_total_amt": 5_000_000_000, "avg_bid_rate": 87.5,
         "female_ceo_flag": True, "disabled_corp_flag": True, "social_corp_flag": True},
        {"brn": "B", "sr_count": 1, "award_count": 5,
         "award_total_amt": 3_000_000_000, "avg_bid_rate": 89.0,
         "female_ceo_flag": True, "disabled_corp_flag": False, "social_corp_flag": False},
        {"brn": "C", "sr_count": 0, "award_count": 8,
         "award_total_amt": 4_000_000_000, "avg_bid_rate": 90.5,
         "female_ceo_flag": False, "disabled_corp_flag": False, "social_corp_flag": False},
        {"brn": "D", "sr_count": 2, "award_count": 2,
         "award_total_amt": 800_000_000, "avg_bid_rate": 92.0,
         "female_ceo_flag": False, "disabled_corp_flag": True, "social_corp_flag": False},
        {"brn": "E", "sr_count": 0, "award_count": 0,
         "award_total_amt": 0, "avg_bid_rate": None,
         "female_ceo_flag": False, "disabled_corp_flag": False, "social_corp_flag": False},
    ]


class TestRuleRankerScore(unittest.TestCase):
    def test_score_without_clusters(self):
        cands = _sample_candidates()
        out = RuleRanker().score(cands)
        self.assertEqual(len(out), 5)
        for r in out:
            self.assertIn("rule_score", r)
            self.assertGreaterEqual(r["rule_score"], 0.0)
            self.assertLessEqual(r["rule_score"], 1.0)
            self.assertEqual(r["score_used"], "rule")
            self.assertIn("axes", r)

    def test_score_with_groups_changes_ranking_input(self):
        """cluster_groups 지정 → composite_score 가 default 와 달라야 함."""
        cands = _sample_candidates()
        out_default = RuleRanker().score(cands)
        out_grouped = RuleRanker().score(
            cands,
            cluster_groups={"A": VETERAN, "B": REAL_SR, "C": DORMANT},
        )
        # 최소 1개 BRN 의 점수가 달라야 함
        diffs = [
            abs(d["rule_score"] - g["rule_score"])
            for d, g in zip(out_default, out_grouped)
        ]
        self.assertGreater(max(diffs), 1e-6)

    def test_known_default_score_topology(self):
        """default 가중치 + 표준 입력 → A (3축 우수) 가 최고점."""
        cands = _sample_candidates()
        out = RuleRanker().score(cands)
        by_brn = {r["brn"]: r["rule_score"] for r in out}
        # A 는 award_count=10 (max), sr=3 (max), demote 면제 → 최고점
        # E 는 sr=0 + 다른 SR 보유 BRN ≥3 → demote 적용 → 음수 clip 후 0
        self.assertGreater(by_brn["A"], by_brn["E"])
        self.assertEqual(by_brn["E"], 0.0)  # demote 적용 + clip


if __name__ == "__main__":
    unittest.main(verbosity=2)
