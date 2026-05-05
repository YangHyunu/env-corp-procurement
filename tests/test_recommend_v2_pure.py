"""
Pure-logic tests for pipeline.recommend_v2 — no DB, no network.

Run:
  uv run python -m unittest tests.test_recommend_v2_pure -v
"""
from __future__ import annotations

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
    def test_full_when_n_samples_ge_3(self):
        budget_won = 1_000_000_000  # 10억
        dist = {"n": 5, "mean": 90.0, "q25": 85.0, "q75": 95.0, "std": 3.0}
        market = {"mean": 92.0}
        ep = _make_expected_price(budget_won, dist, market)
        self.assertEqual(ep["n_samples"], 5)
        self.assertEqual(ep["point"], 900_000_000)
        self.assertEqual(ep["q25"], 850_000_000)
        self.assertEqual(ep["q75"], 950_000_000)
        self.assertEqual(ep["sigma_pp"], 3.0)
        self.assertEqual(ep["market_diff_pp"], -2.0)

    def test_no_interval_when_n_samples_lt_3(self):
        budget_won = 1_000_000_000
        dist = {"n": 2, "mean": 90.0, "q25": 85.0, "q75": 95.0, "std": 3.0}
        market = {"mean": 92.0}
        ep = _make_expected_price(budget_won, dist, market)
        self.assertEqual(ep["n_samples"], 2)
        self.assertEqual(ep["point"], 900_000_000)  # uses BRN mean (n>=1)
        self.assertIsNone(ep["q25"])
        self.assertIsNone(ep["q75"])
        self.assertIsNone(ep["sigma_pp"])
        self.assertIsNone(ep["market_diff_pp"])

    def test_market_fallback_when_brn_dist_empty(self):
        budget_won = 1_000_000_000
        dist = {}  # no BRN samples
        market = {"mean": 88.0}
        ep = _make_expected_price(budget_won, dist, market)
        self.assertEqual(ep["n_samples"], 0)
        self.assertEqual(ep["point"], 880_000_000)  # market mean

    def test_budget_fallback_when_both_empty(self):
        budget_won = 500_000_000
        ep = _make_expected_price(budget_won, dist={}, market={})
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
