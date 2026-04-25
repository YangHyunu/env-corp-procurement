"""
14번 API ingest — raw_g2b_bid_notice 적재.

사용 예:
  uv run python scripts/ingest_bid_notice.py --start 2026-04-01 --end 2026-04-25
  uv run python scripts/ingest_bid_notice.py --start 2026-04-01 --end 2026-04-25 \\
      --dminstt-cd B552584 --dminstt-cd Z008653

DSN 우선순위:
  --dsn 인자 > $DATABASE_URL > postgresql:///eco (로컬 trust)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import find_dotenv, load_dotenv

# repo root을 import path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.g2b_bid_notice import extract_raw_row, iter_items  # noqa: E402
from pipeline.g2b_common import (  # noqa: E402
    ENV_CORP_DMINSTT_CDS,
    ENV_CORP_DMINSTT_NAMES,
    G2BApiError,
    make_session,
    month_windows,
)

load_dotenv(find_dotenv(usecwd=True))

DEFAULT_DSN = os.environ.get("DATABASE_URL", "postgresql:///eco")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("ingest_bid_notice")


# ── PK = (fetched_at, bid_ntce_no, bid_ntce_ord)
#    fetched_at은 DEFAULT now()라 매 실행마다 새 스냅샷이 쌓임 (audit 의도).
#    동일 ms 내 충돌 안전장치로만 ON CONFLICT DO NOTHING.
UPSERT_SQL = """
INSERT INTO raw_g2b_bid_notice (bid_ntce_no, bid_ntce_ord, request_params, item_xml)
VALUES %s
ON CONFLICT (fetched_at, bid_ntce_no, bid_ntce_ord) DO NOTHING
"""


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start", required=True, type=_parse_date, help="YYYY-MM-DD")
    p.add_argument("--end", required=True, type=_parse_date, help="YYYY-MM-DD")
    p.add_argument(
        "--dminstt-cd",
        action="append",
        default=None,
        help="기관 코드 (반복 가능). 미지정 시 환경공단 10개 전체.",
    )
    p.add_argument("--page-size", type=int, default=100)
    p.add_argument("--window-days", type=int, default=28,
                   help="윈도우 길이(일). 기본 28 — 30일도 일부 구간에서 '입력범위 초과' 발생.")
    p.add_argument("--dsn", default=DEFAULT_DSN)
    args = p.parse_args()

    dminstt_cds = args.dminstt_cd or list(ENV_CORP_DMINSTT_CDS)
    windows = list(month_windows(args.start, args.end, days=args.window_days))

    logger.info(
        "start=%s end=%s windows=%d dminstt_cds=%d",
        args.start, args.end, len(windows), len(dminstt_cds),
    )

    session = make_session()

    summary: list[tuple[str, str, int]] = []
    grand_total = 0
    with psycopg2.connect(args.dsn) as conn:
        with conn.cursor() as cur:
            for cd in dminstt_cds:
                name = ENV_CORP_DMINSTT_NAMES.get(cd, cd)
                for bgn, end in windows:
                    rows: list[tuple] = []
                    try:
                        for item, params in iter_items(
                            inqry_bgn_dt=bgn,
                            inqry_end_dt=end,
                            dminstt_cd=cd,
                            page_size=args.page_size,
                            session=session,
                        ):
                            r = extract_raw_row(item, params)
                            if not r["bid_ntce_no"] or not r["bid_ntce_ord"]:
                                logger.warning(
                                    "PK 누락 row skip: cd=%s bgn=%s no=%r ord=%r",
                                    cd, bgn, r["bid_ntce_no"], r["bid_ntce_ord"],
                                )
                                continue
                            rows.append((
                                r["bid_ntce_no"],
                                r["bid_ntce_ord"],
                                psycopg2.extras.Json(r["request_params"]),
                                r["item_xml"],
                            ))
                    except G2BApiError as e:
                        logger.error("API error on %s window=%s..%s: %s", cd, bgn, end, e)
                        return 1

                    if rows:
                        psycopg2.extras.execute_values(cur, UPSERT_SQL, rows)
                        conn.commit()

                    grand_total += len(rows)
                    logger.info(
                        "%s (%s) window=%s..%s inserted=%d",
                        cd, name[:24], bgn[:8], end[:8], len(rows),
                    )
                    summary.append((cd, f"{bgn[:8]}-{end[:8]}", len(rows)))
                    time.sleep(0.15)

    print()
    print("─" * 70)
    print(f"수집 완료: {grand_total} rows / {len(summary)} (dminstt × window)")
    print("─" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
