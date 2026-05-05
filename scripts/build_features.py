"""
mart_features_at_bid 빌드 — 모델 학습용 피처 테이블.

단계:
  1) candidate_pool — (공고, BRN) 페어 정의
  2) BRN 정적 피처 join
  3) BRN 환경공단 누적 PIT (stg_award)
  4) BRN 응찰 패턴 PIT (stg_opening_result + stg_award)
  5) BRN × 품목 PIT
  6) BRN × 권역 PIT
  7) 공고 측 + 시장 구조 PIT
  8) 최종 INSERT

사용:
  uv run python scripts/build_features.py
  uv run python scripts/build_features.py --pool item        # 같은 품목 등록 BRN
  uv run python scripts/build_features.py --pool warm_only   # 환경공단 활동 BRN만 (작음)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import find_dotenv, load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv(find_dotenv(usecwd=True))
DEFAULT_DSN = os.environ.get("DATABASE_URL", "postgresql:///eco")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_features")


# ── Stage 1: candidate_pool ────────────────────────────────────────────
# 학습 단위: (공고, BRN) 페어
# 각 환경공단 공고에 대해 후보 BRN을 정의.
# 옵션 D: 같은 품목 mart_item_supply 등록 BRN ∪ 5번/1번 활동 BRN
SQL_CANDIDATE_POOL = """
DROP TABLE IF EXISTS tmp_candidate_pool;
CREATE TEMP TABLE tmp_candidate_pool AS
WITH env_bids AS (
    SELECT bn.bid_ntce_no, bn.bid_ntce_ord,
           bn.dtil_prdct_clsfc_no AS item_code,
           bn.dminstt_cd,
           bn.openg_dt AS cutoff_date,
           bn.presmpt_prce, bn.asign_bdgt_amt, bn.cntrct_cncls_mthd_nm
    FROM stg_bid_notice bn
    WHERE bn.is_env_corp
      AND bn.dtil_prdct_clsfc_no IS NOT NULL
      AND bn.openg_dt IS NOT NULL
),
-- 같은 품목에 등록된 BRN
item_brns AS (
    SELECT eb.bid_ntce_no, eb.bid_ntce_ord, mis.brn
    FROM env_bids eb
    JOIN mart_item_supply mis ON mis.dtil_prdct_clsfc_no = eb.item_code
)
SELECT DISTINCT eb.bid_ntce_no, eb.bid_ntce_ord, ib.brn,
       eb.item_code, eb.dminstt_cd, eb.cutoff_date,
       eb.presmpt_prce, eb.asign_bdgt_amt, eb.cntrct_cncls_mthd_nm
FROM env_bids eb
JOIN item_brns ib USING (bid_ntce_no, bid_ntce_ord);

CREATE INDEX idx_pool_brn ON tmp_candidate_pool (brn);
CREATE INDEX idx_pool_cutoff ON tmp_candidate_pool (cutoff_date);
CREATE INDEX idx_pool_item ON tmp_candidate_pool (item_code);
"""

SQL_CANDIDATE_POOL_WARM = """
DROP TABLE IF EXISTS tmp_candidate_pool;
CREATE TEMP TABLE tmp_candidate_pool AS
WITH env_bids AS (
    SELECT bn.bid_ntce_no, bn.bid_ntce_ord,
           bn.dtil_prdct_clsfc_no AS item_code,
           bn.dminstt_cd,
           bn.openg_dt AS cutoff_date,
           bn.presmpt_prce, bn.asign_bdgt_amt, bn.cntrct_cncls_mthd_nm
    FROM stg_bid_notice bn
    WHERE bn.is_env_corp
      AND bn.dtil_prdct_clsfc_no IS NOT NULL
      AND bn.openg_dt IS NOT NULL
),
item_brns AS (
    SELECT eb.bid_ntce_no, eb.bid_ntce_ord, mis.brn
    FROM env_bids eb
    JOIN mart_item_supply mis ON mis.dtil_prdct_clsfc_no = eb.item_code
    WHERE mis.award_count > 0  -- warm only
)
SELECT DISTINCT eb.bid_ntce_no, eb.bid_ntce_ord, ib.brn,
       eb.item_code, eb.dminstt_cd, eb.cutoff_date,
       eb.presmpt_prce, eb.asign_bdgt_amt, eb.cntrct_cncls_mthd_nm
FROM env_bids eb
JOIN item_brns ib USING (bid_ntce_no, bid_ntce_ord);

CREATE INDEX idx_pool_brn ON tmp_candidate_pool (brn);
CREATE INDEX idx_pool_cutoff ON tmp_candidate_pool (cutoff_date);
CREATE INDEX idx_pool_item ON tmp_candidate_pool (item_code);
"""


# ── (ii) prefix × warm: 그 공고 prefix4 등록 BRN ∩ 환경공단 활동 BRN ──
SQL_CANDIDATE_POOL_PREFIX_WARM = """
DROP TABLE IF EXISTS tmp_candidate_pool;
CREATE TEMP TABLE tmp_candidate_pool AS
WITH env_bids AS (
    SELECT bn.bid_ntce_no, bn.bid_ntce_ord,
           bn.dtil_prdct_clsfc_no AS item_code,
           LEFT(bn.dtil_prdct_clsfc_no, 4) AS prefix4,
           bn.dminstt_cd,
           bn.openg_dt AS cutoff_date,
           bn.presmpt_prce, bn.asign_bdgt_amt, bn.cntrct_cncls_mthd_nm
    FROM stg_bid_notice bn
    WHERE bn.is_env_corp
      AND bn.dtil_prdct_clsfc_no IS NOT NULL
      AND bn.openg_dt IS NOT NULL
),
warm_brns AS (
    -- 환경공단에서 1번이라도 낙찰받은 BRN
    SELECT DISTINCT bidwinnr_brn AS brn FROM stg_award
    UNION
    -- 또는 5번 1순위로 잡힌 BRN
    SELECT DISTINCT winner_brn FROM stg_opening_result
    WHERE winner_brn IS NOT NULL
),
prefix_brns AS (
    -- 같은 prefix4에 등록한 BRN
    SELECT DISTINCT LEFT(mis.dtil_prdct_clsfc_no, 4) AS prefix4, mis.brn
    FROM mart_item_supply mis
)
SELECT DISTINCT eb.bid_ntce_no, eb.bid_ntce_ord, pb.brn,
       eb.item_code, eb.dminstt_cd, eb.cutoff_date,
       eb.presmpt_prce, eb.asign_bdgt_amt, eb.cntrct_cncls_mthd_nm
FROM env_bids eb
JOIN prefix_brns pb ON pb.prefix4 = eb.prefix4
JOIN warm_brns wb   ON wb.brn = pb.brn;

CREATE INDEX idx_pool_brn ON tmp_candidate_pool (brn);
CREATE INDEX idx_pool_cutoff ON tmp_candidate_pool (cutoff_date);
CREATE INDEX idx_pool_item ON tmp_candidate_pool (item_code);
"""


# ── Stage 2~7: 단일 INSERT로 모든 피처 계산 (LATERAL 서브쿼리) ──
# 한 번에 INSERT — point-in-time 보장 (cutoff_date 기준 stg_award 필터)
SQL_INSERT_FEATURES = """
TRUNCATE mart_features_at_bid;

INSERT INTO mart_features_at_bid (
    bid_ntce_no, bid_ntce_ord, brn,
    is_winner, participated_in_bid,
    corp_size, is_manufacturer, region_code, g2b_age_years,
    female_ceo_flag, disabled_corp_flag, social_corp_flag, real_sr_flag,
    env_award_count_pit, env_award_amt_pit, env_avg_rate_pit,
    env_dminstt_count_pit, env_recent_1y_count_pit, days_since_last_award_pit,
    bid_top1_count_pit, bid_lost_count_pit, bid_lost_ratio_pit, bid_recent_lost_count_pit,
    brn_item_award_count_pit, brn_item_avg_rate_pit, main_prdct_match,
    brn_dminstt_award_count_pit,
    presmpt_prce, asign_bdgt_amt, cntrct_cncls_mthd_nm,
    bid_month, bid_quarter, bid_dminstt_cd, bid_dtil_prdct_no,
    item_pool_density_pit, item_recent_unmet_pit, item_top1_concentration_pit,
    cutoff_date
)
SELECT
    p.bid_ntce_no, p.bid_ntce_ord, p.brn,

    -- Y 라벨
    COALESCE(a_final.brn IS NOT NULL, false) AS is_winner,
    COALESCE(o_top1.brn IS NOT NULL, false) AS participated_in_bid,

    -- A. BRN 정적
    m.corp_size,
    m.is_manufacturer,
    m.region_code,
    CASE WHEN m.g2b_registered_at IS NOT NULL
         THEN EXTRACT(EPOCH FROM (p.cutoff_date - m.g2b_registered_at::timestamptz)) / (365.25*86400)
         END::numeric(5,2) AS g2b_age_years,
    s.female_ceo_flag,
    s.disabled_corp_flag,
    s.social_corp_flag,
    (s.disabled_corp_flag OR s.social_corp_flag) AS real_sr_flag,

    -- B. BRN env-award PIT
    COALESCE(env_pit.cnt, 0)         AS env_award_count_pit,
    COALESCE(env_pit.amt, 0)         AS env_award_amt_pit,
    env_pit.avg_rate                 AS env_avg_rate_pit,
    COALESCE(env_pit.dminstt_cnt, 0) AS env_dminstt_count_pit,
    COALESCE(env_pit.recent_1y, 0)   AS env_recent_1y_count_pit,
    env_pit.days_since                AS days_since_last_award_pit,

    -- C. BRN bid pattern PIT (5번 1순위 + 1번 탈락)
    COALESCE(bid_pit.top1_cnt, 0)        AS bid_top1_count_pit,
    COALESCE(bid_pit.lost_cnt, 0)        AS bid_lost_count_pit,
    bid_pit.lost_ratio                    AS bid_lost_ratio_pit,
    COALESCE(bid_pit.recent_lost, 0)     AS bid_recent_lost_count_pit,

    -- D. BRN × 품목 PIT
    COALESCE(item_pit.cnt, 0) AS brn_item_award_count_pit,
    item_pit.avg_rate          AS brn_item_avg_rate_pit,
    COALESCE(m.main_dtil_prdct_cd = p.item_code, false) AS main_prdct_match,

    -- E. BRN × 권역 PIT
    COALESCE(dminstt_pit.cnt, 0) AS brn_dminstt_award_count_pit,

    -- F. 공고 측
    p.presmpt_prce,
    p.asign_bdgt_amt,
    p.cntrct_cncls_mthd_nm,
    EXTRACT(MONTH FROM p.cutoff_date)::smallint   AS bid_month,
    EXTRACT(QUARTER FROM p.cutoff_date)::smallint AS bid_quarter,
    p.dminstt_cd,
    p.item_code,

    -- G. 시장 구조 PIT
    COALESCE(market_pit.pool_density, 0)    AS item_pool_density_pit,
    market_pit.recent_unmet                  AS item_recent_unmet_pit,
    market_pit.top1_concentration            AS item_top1_concentration_pit,

    p.cutoff_date

FROM tmp_candidate_pool p

-- A. BRN 정적
LEFT JOIN mart_company_master m ON m.brn = p.brn
LEFT JOIN mart_company_sr     s ON s.brn = p.brn

-- Y: 1번 final winner
LEFT JOIN LATERAL (
    SELECT a.bidwinnr_brn AS brn
    FROM stg_award a
    WHERE a.bid_ntce_no = p.bid_ntce_no
      AND a.bid_ntce_ord = p.bid_ntce_ord
      AND a.bidwinnr_brn = p.brn
    LIMIT 1
) a_final ON true

-- 5번 winner (참여)
LEFT JOIN LATERAL (
    SELECT o.winner_brn AS brn
    FROM stg_opening_result o
    WHERE o.bid_ntce_no = p.bid_ntce_no
      AND o.bid_ntce_ord = p.bid_ntce_ord
      AND o.winner_brn = p.brn
    LIMIT 1
) o_top1 ON true

-- B. env_award PIT — 그 BRN의 cutoff 이전 환경공단 낙찰
LEFT JOIN LATERAL (
    SELECT
        COUNT(*)                               AS cnt,
        COALESCE(SUM(a.sucsfbid_amt), 0)::bigint AS amt,
        AVG(a.sucsfbid_rate)::numeric(6,3)     AS avg_rate,
        COUNT(DISTINCT a.dminstt_cd)           AS dminstt_cnt,
        SUM(CASE WHEN a.fnl_sucsf_date >= (p.cutoff_date - INTERVAL '1 year')::date
                 THEN 1 ELSE 0 END)            AS recent_1y,
        EXTRACT(DAY FROM (p.cutoff_date - MAX(a.fnl_sucsf_date)::timestamptz))::int AS days_since
    FROM stg_award a
    WHERE a.bidwinnr_brn = p.brn
      AND a.fnl_sucsf_date IS NOT NULL
      AND a.fnl_sucsf_date < p.cutoff_date::date
) env_pit ON true

-- C. bid pattern PIT — 5번 1순위 + 1번 탈락 패턴
LEFT JOIN LATERAL (
    WITH top1_history AS (
        SELECT o.bid_ntce_no, o.bid_ntce_ord, o.bid_clsfc_no, o.rbid_no, o.openg_dt
        FROM stg_opening_result o
        WHERE o.winner_brn = p.brn
          AND o.openg_dt < p.cutoff_date
    ),
    awards AS (
        SELECT a.bid_ntce_no, a.bid_ntce_ord, a.bid_clsfc_no, a.rbid_no, a.bidwinnr_brn
        FROM stg_award a
    )
    SELECT
        COUNT(*) AS top1_cnt,
        SUM(CASE WHEN aw.bidwinnr_brn IS NOT NULL AND aw.bidwinnr_brn != p.brn
                 THEN 1 ELSE 0 END) AS lost_cnt,
        CASE WHEN COUNT(*) > 0
             THEN (SUM(CASE WHEN aw.bidwinnr_brn IS NOT NULL AND aw.bidwinnr_brn != p.brn
                            THEN 1 ELSE 0 END)::numeric / COUNT(*))::numeric(4,3)
             END AS lost_ratio,
        SUM(CASE WHEN aw.bidwinnr_brn IS NOT NULL AND aw.bidwinnr_brn != p.brn
                  AND th.openg_dt >= p.cutoff_date - INTERVAL '1 year'
                 THEN 1 ELSE 0 END) AS recent_lost
    FROM top1_history th
    LEFT JOIN awards aw USING (bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no)
) bid_pit ON true

-- D. BRN × 품목 PIT
LEFT JOIN LATERAL (
    SELECT
        COUNT(*) AS cnt,
        AVG(a.sucsfbid_rate)::numeric(6,3) AS avg_rate
    FROM stg_award a
    JOIN stg_bid_notice bn USING (bid_ntce_no, bid_ntce_ord)
    WHERE a.bidwinnr_brn = p.brn
      AND bn.dtil_prdct_clsfc_no = p.item_code
      AND a.fnl_sucsf_date IS NOT NULL
      AND a.fnl_sucsf_date < p.cutoff_date::date
) item_pit ON true

-- E. BRN × 권역 PIT
LEFT JOIN LATERAL (
    SELECT COUNT(*) AS cnt
    FROM stg_award a
    WHERE a.bidwinnr_brn = p.brn
      AND a.dminstt_cd = p.dminstt_cd
      AND a.fnl_sucsf_date IS NOT NULL
      AND a.fnl_sucsf_date < p.cutoff_date::date
) dminstt_pit ON true

-- G. 시장 구조 PIT — 그 품목 cutoff 시점
LEFT JOIN LATERAL (
    WITH item_awards AS (
        SELECT a.*
        FROM stg_award a
        JOIN stg_bid_notice bn USING (bid_ntce_no, bid_ntce_ord)
        WHERE bn.dtil_prdct_clsfc_no = p.item_code
          AND a.fnl_sucsf_date IS NOT NULL
          AND a.fnl_sucsf_date < p.cutoff_date::date
    ),
    item_openings AS (
        SELECT o.*
        FROM stg_opening_result o
        JOIN stg_bid_notice bn USING (bid_ntce_no, bid_ntce_ord)
        WHERE bn.dtil_prdct_clsfc_no = p.item_code
          AND o.openg_dt < p.cutoff_date
          AND o.openg_dt >= p.cutoff_date - INTERVAL '1 year'
    ),
    top1_share AS (
        SELECT bidwinnr_brn, COUNT(*) AS w
        FROM item_awards GROUP BY 1
    )
    SELECT
        (SELECT COUNT(DISTINCT bidwinnr_brn) FROM item_awards) AS pool_density,
        CASE WHEN (SELECT COUNT(*) FROM item_openings) > 0
             THEN ((SELECT SUM(CASE WHEN progrs_div_cd_nm='유찰' THEN 1 ELSE 0 END)::numeric
                    FROM item_openings) /
                   (SELECT COUNT(*) FROM item_openings)::numeric)::numeric(4,3)
             END AS recent_unmet,
        CASE WHEN (SELECT COUNT(*) FROM item_awards) > 0
             THEN ((SELECT MAX(w)::numeric FROM top1_share) /
                   (SELECT COUNT(*) FROM item_awards)::numeric)::numeric(4,3)
             END AS top1_concentration
) market_pit ON true
;
"""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pool", choices=["item", "warm_only", "prefix_warm"],
                   default="prefix_warm",
                   help="후보 풀 정의 (default: prefix_warm — prefix4 도메인 안의 warm BRN)")
    p.add_argument("--dsn", default=DEFAULT_DSN)
    args = p.parse_args()

    pool_sql = {
        "item":         SQL_CANDIDATE_POOL,
        "warm_only":    SQL_CANDIDATE_POOL_WARM,
        "prefix_warm":  SQL_CANDIDATE_POOL_PREFIX_WARM,
    }[args.pool]

    with psycopg2.connect(args.dsn) as conn:
        with conn.cursor() as cur:
            logger.info("[1/3] candidate_pool 만들기 (--pool=%s)...", args.pool)
            cur.execute(pool_sql)
            cur.execute("SELECT COUNT(*) FROM tmp_candidate_pool")
            pool_n = cur.fetchone()[0]
            logger.info("       candidate pairs: %s", f"{pool_n:,}")

            logger.info("[2/3] mart_features_at_bid 빌드... (~1~2분 예상)")
            cur.execute(SQL_INSERT_FEATURES)
            conn.commit()

            cur.execute("SELECT COUNT(*) FROM mart_features_at_bid")
            n = cur.fetchone()[0]
            logger.info("       inserted: %s rows", f"{n:,}")

            logger.info("[3/3] 검증")
            cur.execute("""
                SELECT
                  COUNT(*) AS total,
                  SUM(CASE WHEN is_winner THEN 1 ELSE 0 END) AS pos,
                  ROUND(100.0*SUM(CASE WHEN is_winner THEN 1 ELSE 0 END)/COUNT(*),3) AS pos_pct,
                  SUM(CASE WHEN participated_in_bid THEN 1 ELSE 0 END) AS hard_neg,
                  COUNT(DISTINCT bid_ntce_no) AS bids,
                  COUNT(DISTINCT brn) AS brns
                FROM mart_features_at_bid
            """)
            r = cur.fetchone()
            logger.info("       total=%s, pos=%s (%.3f%%), hard_neg=%s, bids=%s, brns=%s",
                        f"{r[0]:,}", r[1], r[2], f"{r[3]:,}", r[4], f"{r[5]:,}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
