"""
mart_item_supply 빌드 — (세부품명번호, BRN) 단위 와이드 테이블.

스코프: 환경공단이 1년 내 발주한 150개 품목에 한정 (신규 품목은 후속 확장).
  - csv_pool      = mart_company_master.main_dtil_prdct_cd 매칭 (공급 가능 풀)
  - award_agg     = stg_bid_notice JOIN stg_award (환경공단 낙찰 실적 집계)
  - supply_source = csv_main / award_history / both

사용:
  uv run python scripts/build_mart_item_supply.py
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import find_dotenv, load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv(find_dotenv(usecwd=True))
DEFAULT_DSN = os.environ.get("DATABASE_URL", "postgresql:///eco")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_mart_item_supply")


BUILD_SQL = """
TRUNCATE mart_item_supply;

WITH env_items AS (
    SELECT DISTINCT dtil_prdct_clsfc_no
    FROM stg_bid_notice
    WHERE is_env_corp AND dtil_prdct_clsfc_no IS NOT NULL
), csv_pool AS (
    SELECT m.main_dtil_prdct_cd AS dtil_prdct_clsfc_no,
           m.brn
    FROM mart_company_master m
    JOIN env_items e ON e.dtil_prdct_clsfc_no = m.main_dtil_prdct_cd
), award_agg AS (
    SELECT
        b.dtil_prdct_clsfc_no,
        a.bidwinnr_brn AS brn,
        COUNT(*)::INTEGER                                    AS award_count,
        COALESCE(SUM(a.sucsfbid_amt), 0)::BIGINT            AS award_total_amt,
        ROUND(AVG(a.sucsfbid_rate)::NUMERIC, 3)             AS avg_bid_rate,
        MIN(a.rl_openg_dt)                                   AS first_award_at,
        MAX(a.rl_openg_dt)                                   AS last_award_at
    FROM stg_award a
    JOIN stg_bid_notice b USING (bid_ntce_no, bid_ntce_ord)
    WHERE b.is_env_corp AND b.dtil_prdct_clsfc_no IS NOT NULL
    GROUP BY 1, 2
), unioned AS (
    SELECT dtil_prdct_clsfc_no, brn FROM csv_pool
    UNION
    SELECT dtil_prdct_clsfc_no, brn FROM award_agg
)
INSERT INTO mart_item_supply (
    dtil_prdct_clsfc_no, brn, supply_source,
    award_count, award_total_amt, avg_bid_rate,
    first_award_at, last_award_at, last_synced_at
)
SELECT
    u.dtil_prdct_clsfc_no,
    u.brn,
    CASE
        WHEN c.brn IS NOT NULL AND a.brn IS NOT NULL THEN 'both'
        WHEN c.brn IS NOT NULL                       THEN 'csv_main'
        ELSE                                              'award_history'
    END AS supply_source,
    COALESCE(a.award_count, 0),
    COALESCE(a.award_total_amt, 0),
    a.avg_bid_rate,
    a.first_award_at,
    a.last_award_at,
    now()
FROM unioned u
LEFT JOIN csv_pool  c USING (dtil_prdct_clsfc_no, brn)
LEFT JOIN award_agg a USING (dtil_prdct_clsfc_no, brn);
"""


def main() -> int:
    with psycopg2.connect(DEFAULT_DSN) as conn:
        with conn.cursor() as cur:
            logger.info("mart_item_supply 빌드 시작...")
            cur.execute(BUILD_SQL)

            cur.execute("SELECT COUNT(*) FROM mart_item_supply")
            n_total = cur.fetchone()[0]

            cur.execute("""
                SELECT supply_source, COUNT(*)
                FROM mart_item_supply GROUP BY 1 ORDER BY 2 DESC
            """)
            by_source = cur.fetchall()

            cur.execute("SELECT COUNT(DISTINCT dtil_prdct_clsfc_no) FROM mart_item_supply")
            distinct_items = cur.fetchone()[0]

            cur.execute("SELECT COUNT(DISTINCT brn) FROM mart_item_supply")
            distinct_brn = cur.fetchone()[0]
        conn.commit()

    print()
    print("─" * 70)
    print(f"mart_item_supply        = {n_total:,} rows")
    print(f"distinct dtil_prdct_cd  = {distinct_items:,}")
    print(f"distinct brn            = {distinct_brn:,}")
    print()
    print(f"{'supply_source':<16} {'count':>8}")
    for src, cnt in by_source:
        print(f"  {src:<14} {cnt:>8d}")
    print("─" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
