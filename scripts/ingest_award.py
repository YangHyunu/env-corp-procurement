"""
1번 API ingest — raw_g2b_award 적재.

소스: raw_g2b_bid_notice의 distinct bidNtceNo (가장 최근 fetched_at 기준).
호출 패턴: inqryDiv=4 + bidNtceNo (1:N 룩업, 보통 N=1).

사용:
  uv run python scripts/ingest_award.py
  uv run python scripts/ingest_award.py --limit 10        # 테스트
  uv run python scripts/ingest_award.py --skip-empty      # totalCount=0 로깅 생략

DSN 우선순위:
  --dsn 인자 > $DATABASE_URL > postgresql:///eco
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import find_dotenv, load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.g2b_award import extract_raw_row, iter_items_for_bid  # noqa: E402
from pipeline.g2b_common import G2BApiError, make_session  # noqa: E402

load_dotenv(find_dotenv(usecwd=True))

DEFAULT_DSN = os.environ.get("DATABASE_URL", "postgresql:///eco")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("ingest_award")


SOURCE_SQL = """
SELECT DISTINCT bid_ntce_no
FROM raw_g2b_bid_notice
ORDER BY bid_ntce_no
"""

# raw_g2b_award PK = (fetched_at, bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no)
# fetched_at은 DEFAULT now() — 매 실행 새 스냅샷.
UPSERT_SQL = """
INSERT INTO raw_g2b_award
    (bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no, request_params, item_xml)
VALUES %s
ON CONFLICT (fetched_at, bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no) DO NOTHING
"""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--limit", type=int, default=None, help="bidNtceNo 처리 상한 (테스트용)")
    p.add_argument("--skip-empty", action="store_true", help="totalCount=0 로그 생략")
    p.add_argument("--dsn", default=DEFAULT_DSN)
    p.add_argument("--page-size", type=int, default=999)
    args = p.parse_args()

    with psycopg2.connect(args.dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(SOURCE_SQL)
            bids = [row[0] for row in cur.fetchall()]

    if args.limit:
        bids = bids[: args.limit]

    if not bids:
        logger.error("raw_g2b_bid_notice 비어있음. 14번 ingest 먼저.")
        return 1

    logger.info("총 %d개 bidNtceNo 처리 시작", len(bids))

    session = make_session()
    hit = 0
    miss = 0
    inserted_total = 0

    with psycopg2.connect(args.dsn) as conn:
        with conn.cursor() as cur:
            for i, no in enumerate(bids, 1):
                rows: list[tuple] = []
                try:
                    for item, params in iter_items_for_bid(
                        no, page_size=args.page_size, session=session
                    ):
                        r = extract_raw_row(item, params)
                        if not all((r["bid_ntce_no"], r["bid_ntce_ord"],
                                    r["bid_clsfc_no"], r["rbid_no"])):
                            logger.warning(
                                "PK 누락 row skip: no=%s pk=(%r,%r,%r,%r)",
                                no, r["bid_ntce_no"], r["bid_ntce_ord"],
                                r["bid_clsfc_no"], r["rbid_no"],
                            )
                            continue
                        rows.append((
                            r["bid_ntce_no"],
                            r["bid_ntce_ord"],
                            r["bid_clsfc_no"],
                            r["rbid_no"],
                            psycopg2.extras.Json(r["request_params"]),
                            r["item_xml"],
                        ))
                except G2BApiError as e:
                    logger.error("API error on %s: %s", no, e)
                    return 1

                if rows:
                    psycopg2.extras.execute_values(cur, UPSERT_SQL, rows)
                    conn.commit()
                    hit += 1
                    inserted_total += len(rows)
                    logger.info("[%d/%d] %s  awards=%d", i, len(bids), no, len(rows))
                else:
                    miss += 1
                    if not args.skip_empty:
                        logger.info("[%d/%d] %s  awards=0 (개찰 미완료/유찰 추정)",
                                    i, len(bids), no)

                time.sleep(0.1)

    print()
    print("─" * 70)
    print(f"hit  : {hit}/{len(bids)} ({hit / len(bids) * 100:.1f}%)")
    print(f"miss : {miss}/{len(bids)} ({miss / len(bids) * 100:.1f}%)")
    print(f"inserted rows: {inserted_total}")
    print("─" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
