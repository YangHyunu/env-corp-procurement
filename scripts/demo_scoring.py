"""
demo_scoring.py — pipeline.scoring.score() 데모.

3개 샘플 품목으로 추천 결과 출력 + 가중치 슬라이더 변형 시뮬레이션.

품목 후보:
  4015151301  수중펌프            (438 BRN 풀, 6 award)
  3010990401  순환골재            (303 BRN 풀, 9 award)
  2611170403  전기차충전장치      (203 BRN 풀, 3 award)

사용:
  uv run python scripts/demo_scoring.py
  uv run python scripts/demo_scoring.py --item 4015151301 --top-k 7
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.scoring import (  # noqa: E402
    DEFAULT_WEIGHTS,
    SrFilter,
    score,
)


SAMPLE_ITEMS = [
    ("4015151301", "수중펌프"),
    ("3010990401", "순환골재"),
    ("2611170403", "전기차충전장치"),
]


def render(result, label: str) -> None:
    print(f"\n{'═' * 78}")
    print(f"[{label}]  item={result.item_code}  matched={result.matched_count}"
          f"  SR coverage={result.sr_coverage_pct:.1f}%"
          f"  sr_floor={'ON' if result.meta.get('sr_floor_active') else 'off'}")
    print("═" * 78)
    if not result.recommendations:
        print(f"  ⚠️  {result.meta}")
        return
    print(f"{'#':>2} {'BRN':<11} {'corp_name':<32} {'score':>6}"
          f" {'SR':>3} {'award':>5} {'rate':>5}  badges")
    print("-" * 78)
    for r in result.recommendations:
        rate = "" if r.award_summary["avg_rate"] is None else f"{r.award_summary['avg_rate']:.1f}"
        badges = "/".join(r.sr_badges) if r.sr_badges else "-"
        suffix = " (SR demoted)" if r.is_sr_demoted else ""
        print(f"{r.rank:>2} {r.brn:<11} {r.corp_name[:30]:<32} {r.composite_score:>6.3f}"
              f" {sum(1 for _ in r.sr_badges):>3d}"
              f" {r.award_summary['count']:>5d}"
              f" {rate:>5}"
              f"  {badges}{suffix}")
    # 1위 reason
    top = result.recommendations[0]
    print()
    print(f"  Top1 reason : {top.reason}")
    print(f"  Top1 axes   : "
          f"공급={top.axes['supply_stability']:.2f} "
          f"SR={top.axes['sr_diversity']:.2f} "
          f"실적={top.axes['track_record']:.2f} "
          f"리스크={top.axes['risk_free']:.2f}* "
          f"군집={top.axes['cluster_fit']:.2f}*  (* = MVP stub)")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--item", default=None, help="단일 품목 코드만 테스트")
    p.add_argument("--top-k", type=int, default=5)
    args = p.parse_args()

    items = [(args.item, "(custom)")] if args.item else SAMPLE_ITEMS

    for code, name in items:
        # 1) 기본 가중치
        result = score(code, top_k=args.top_k)
        render(result, f"DEFAULT  {name}")

        # 2) SR 강조 슬라이더 (sr_diversity 0.50 ↑)
        sr_heavy = {
            "sr_diversity":          0.50,
            "track_record":          0.20,
            "price_competitiveness": 0.15,
            "supply_stability":      0.15,
        }
        result = score(code, weights=sr_heavy, top_k=args.top_k)
        render(result, f"SR-HEAVY  {name}")

        # 3) require_any_sr 필터
        result = score(
            code,
            sr_filter=SrFilter(require_any_sr=True),
            top_k=args.top_k,
        )
        render(result, f"SR-ONLY  {name}")

    print("\n" + "═" * 78)
    print(f"DEFAULT_WEIGHTS = {DEFAULT_WEIGHTS}")
    print("═" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
