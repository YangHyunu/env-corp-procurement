"""
Pure-logic tests for pipeline.recommend_v2 — no DB, no network.

Run:
  uv run python -m unittest tests.test_recommend_v2_pure -v

baseline 회귀 테스트 (TestRecommendBaselineRegression) 는 DB + fixture 두 가지가
모두 있을 때만 실행된다. fixture 생성:
  uv run python scripts/dump_recommend_baseline.py
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.recommend_v2 import (  # noqa: E402
    DORMANT_MONTHS,
    PRECEDENT_BUDGET_HI,
    PRECEDENT_BUDGET_LO,
    RISK_LOST_HARD,
    RISK_RECENT_LOST,
    TIER_A_CUTOFF,
    TIER_B_CUTOFF,
    _dormant_months,
    _make_charts,
    _make_expected_price,
    _make_risk_info,
    _make_supply_stability,
    _risk_grade,
    _tier,
)


class TestRiskGrade(unittest.TestCase):
    def test_safe_when_top1_high_no_loss(self):
        self.assertEqual(_risk_grade(top1=5, lost=0, recent_lost=0), "안전")

    def test_unknown_when_no_top1(self):
        self.assertEqual(_risk_grade(top1=0, lost=0, recent_lost=0), "미확인")

    def test_caution_when_lost_hard_cap(self):
        self.assertEqual(
            _risk_grade(top1=10, lost=RISK_LOST_HARD, recent_lost=0), "주의"
        )

    def test_caution_when_lost_ratio(self):
        # 4 / 10 = 0.40 ≥ 0.30
        self.assertEqual(_risk_grade(top1=10, lost=4, recent_lost=0), "주의")

    def test_caution_when_recent_lost(self):
        self.assertEqual(
            _risk_grade(top1=10, lost=1, recent_lost=RISK_RECENT_LOST), "주의"
        )

    def test_ok_otherwise(self):
        self.assertEqual(_risk_grade(top1=5, lost=1, recent_lost=0), "양호")


class TestTier(unittest.TestCase):
    def test_a(self):
        self.assertEqual(_tier(TIER_A_CUTOFF, "양호"), "A")
        self.assertEqual(_tier(0.99, "안전"), "A")

    def test_b(self):
        self.assertEqual(_tier(TIER_B_CUTOFF, "양호"), "B")
        self.assertEqual(_tier(0.45, "안전"), "B")

    def test_c_low_score(self):
        self.assertEqual(_tier(0.1, "양호"), "C")

    def test_c_overrides_when_caution(self):
        # 주의 등급은 점수와 무관하게 C
        self.assertEqual(_tier(0.99, "주의"), "C")
        self.assertEqual(_tier(0.0, "주의"), "C")


class TestDormantMonths(unittest.TestCase):
    def test_none_when_no_last_award(self):
        self.assertIsNone(_dormant_months(None))

    def test_zero_when_today(self):
        self.assertEqual(_dormant_months(date.today()), 0)

    def test_naive_datetime(self):
        d = datetime.now() - timedelta(days=60)
        m = _dormant_months(d)
        self.assertIsNotNone(m)
        self.assertGreaterEqual(m, 1)


class TestMakeExpectedPrice(unittest.TestCase):
    """_make_expected_price(budget_won, dist, dist_at_scale, market, market_at_scale) 테스트.

    dist/dist_at_scale: BRN 전체/유사 규모 분포
    market/market_at_scale: 시장 전체/유사 규모 baseline
    """

    def test_full_when_n_samples_ge_3(self):
        budget_won = 1_000_000_000  # 10억
        # 유사 규모 n≥3 → Fallback 1 (가장 정확)
        dist_at_scale = {"n": 5, "mean": 90.0, "q25": 85.0, "q75": 95.0, "std": 3.0}
        dist = {"n": 5, "mean": 90.0}
        market_at_scale = {"n": 10, "mean": 92.0, "q25": 88.0, "q50": 91.0, "q75": 94.0}
        market = {"mean": 92.0}
        ep = _make_expected_price(budget_won, dist, dist_at_scale, market, market_at_scale)
        self.assertEqual(ep["n_samples"], 5)
        self.assertEqual(ep["point"], 900_000_000)
        self.assertEqual(ep["q25"], 850_000_000)
        self.assertEqual(ep["q75"], 950_000_000)
        self.assertEqual(ep["sigma_pp"], 3.0)
        self.assertEqual(ep["market_diff_pp"], -2.0)
        # 시장 분위수 — market_at_scale n≥3 → 채워짐
        self.assertIsNotNone(ep["market_q25_million"])
        self.assertIsNotNone(ep["market_q50_million"])
        self.assertIsNotNone(ep["market_q75_million"])

    def test_no_interval_when_n_samples_lt_3(self):
        budget_won = 1_000_000_000
        # 유사 규모 n=2 → Fallback 2 (점추정만 — sigma/q25/q75 X)
        dist_at_scale = {"n": 2, "mean": 90.0, "q25": 85.0, "q75": 95.0, "std": 3.0}
        dist = {"n": 2, "mean": 90.0}
        market_at_scale = {"n": 0}
        market = {"mean": 92.0}
        ep = _make_expected_price(budget_won, dist, dist_at_scale, market, market_at_scale)
        self.assertEqual(ep["n_samples"], 2)
        self.assertEqual(ep["point"], 900_000_000)  # uses BRN mean (n>=1)
        self.assertIsNone(ep["q25"])
        self.assertIsNone(ep["q75"])
        self.assertIsNone(ep["sigma_pp"])
        # n=2, extrapolated=False, ref_market_mean=92.0 → market_diff_pp 계산됨 (정상 동작)
        self.assertEqual(ep["market_diff_pp"], -2.0)
        # market_at_scale n=0 → 시장 분위수 None
        self.assertIsNone(ep["market_q25_million"])
        self.assertIsNone(ep["market_q50_million"])
        self.assertIsNone(ep["market_q75_million"])

    def test_market_fallback_when_brn_dist_empty(self):
        budget_won = 1_000_000_000
        dist = {}  # no BRN samples
        dist_at_scale = {}
        market_at_scale = {}
        market = {"mean": 88.0}
        ep = _make_expected_price(budget_won, dist, dist_at_scale, market, market_at_scale)
        self.assertEqual(ep["n_samples"], 0)
        self.assertEqual(ep["point"], 880_000_000)  # market mean

    def test_budget_fallback_when_both_empty(self):
        budget_won = 500_000_000
        ep = _make_expected_price(budget_won, dist={}, dist_at_scale={}, market={}, market_at_scale={})
        self.assertEqual(ep["n_samples"], 0)
        self.assertEqual(ep["point"], budget_won)


class TestMakeRiskInfo(unittest.TestCase):
    def test_dormant_threshold(self):
        # last_award 30 months ago → dormant
        old = date.today() - timedelta(days=int(30 * 30.4))
        ri = _make_risk_info(old, {"top1_count": 3, "lost_count": 0, "recent_lost": 0})
        self.assertGreaterEqual(ri["dormant_months"], DORMANT_MONTHS)
        self.assertTrue(ri["is_dormant"])

    def test_not_dormant_when_recent(self):
        recent = date.today() - timedelta(days=30)
        ri = _make_risk_info(recent, {"top1_count": 3, "lost_count": 0, "recent_lost": 0})
        self.assertFalse(ri["is_dormant"])

    def test_lost_ratio_rounded(self):
        ri = _make_risk_info(None, {"top1_count": 3, "lost_count": 1, "recent_lost": 0})
        self.assertEqual(ri["lost_ratio"], round(1 / 3, 3))

    def test_zero_top1_safe_division(self):
        ri = _make_risk_info(None, {"top1_count": 0, "lost_count": 0, "recent_lost": 0})
        self.assertEqual(ri["lost_ratio"], 0.0)
        self.assertEqual(ri["grade"], "미확인")


class TestMakeSupplyStability(unittest.TestCase):
    def test_g2b_age_computed(self):
        c = {
            "g2b_registered_at": date.today() - timedelta(days=int(365.25 * 5)),
            "award_total_amt": 100_000_000,
            "is_manufacturer": True,
            "last_award_at": None,
        }
        ss = _make_supply_stability(c, brn="1234567890")
        self.assertAlmostEqual(ss["g2b_age_years"], 5.0, delta=0.1)
        self.assertTrue(ss["is_manufacturer"])

    def test_g2b_age_none_when_no_reg(self):
        ss = _make_supply_stability({"g2b_registered_at": None}, brn="x")
        self.assertIsNone(ss["g2b_age_years"])

    def test_g2b_age_logs_when_invalid_type(self):
        # Passing an int (not date) → TypeError when subtracting → caught + logged
        ss = _make_supply_stability({"g2b_registered_at": 12345}, brn="x")
        self.assertIsNone(ss["g2b_age_years"])


class TestMakeCharts(unittest.TestCase):
    def test_empty_dist(self):
        ch = _make_charts({})
        self.assertEqual(ch, {"bid_rate_distribution": [], "bid_amt_distribution": []})

    def test_with_data(self):
        ch = _make_charts({"rates": [90.0, 92.5], "amts": [100_000_000, 110_000_000]})
        self.assertEqual(ch["bid_rate_distribution"], [90.0, 92.5])
        self.assertEqual(ch["bid_amt_distribution"], [100_000_000, 110_000_000])


class TestPrecedentConstants(unittest.TestCase):
    """Sanity: bracket constants should sandwich budget."""

    def test_brackets_make_sense(self):
        self.assertLess(PRECEDENT_BUDGET_LO, 1.0)
        self.assertGreater(PRECEDENT_BUDGET_HI, 1.0)


FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "recommend_v2_baseline.json"
)


def _db_available() -> bool:
    """psycopg2.connect 가 즉시 성공하는지만 확인. 통합 PR 의 점수·랭킹 회귀 검출용."""
    try:
        import psycopg2
        dsn = os.environ.get("DATABASE_URL", "postgresql:///eco")
        conn = psycopg2.connect(dsn, connect_timeout=2)
        conn.close()
        return True
    except Exception:
        return False


@unittest.skipUnless(
    FIXTURE_PATH.exists() and _db_available(),
    "baseline fixture 또는 DB 부재 — scripts/dump_recommend_baseline.py 로 fixture 생성 후 재실행",
)
class TestRecommendBaselineRegression(unittest.TestCase):
    """회귀 baseline — 통합 PR(D1.B / D3.B / D3.C) 에서 점수·랭킹·tier 변화 검출."""

    @classmethod
    def setUpClass(cls) -> None:
        from scripts.dump_recommend_baseline import (  # noqa: E402
            CASES, SR_FILTER_NO, _snapshot_response,
        )
        from pipeline.recommend_v2 import RecommendV2Request, recommend  # noqa: E402
        cls._cases = CASES
        cls._sr = SR_FILTER_NO
        cls._snapshot = staticmethod(_snapshot_response)
        cls._recommend = staticmethod(recommend)
        cls._req_cls = RecommendV2Request
        cls._baseline = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_recommend_v2_matches_baseline(self):
        for keyword, budget_million in self._cases:
            with self.subTest(keyword=keyword, budget=budget_million):
                key = f"{keyword}__{budget_million}M"
                expected = self._baseline.get(key)
                self.assertIsNotNone(expected, f"baseline 누락: {key}")
                req = self._req_cls(
                    item_keyword=keyword,
                    budget_million_won=budget_million,
                    sr_filter=self._sr,
                    top_k=5,
                )
                actual = self._snapshot(self._recommend(req))
                self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
