"""
조달업체 등록 내역 CSV 적재 — raw → stg → mart_company_master + mart_company_sr.

medallion 패턴:
  - raw_procurement_corp  : CSV row 단위 JSONB 보존 (선택, --skip-raw로 생략)
  - stg_procurement_corp  : 정규화 (BRN/SR/품명번호) — TRUNCATE + INSERT
  - mart_company_master   : BRN 단위 1행, 본사 우선, 국내만 — TRUNCATE + INSERT
  - mart_company_sr       : BRN 단위 SR 매트릭스 (1차) — TRUNCATE + INSERT

사용:
  uv run python scripts/ingest_procurement_corp.py data/raw/procurement_corp_20260425.csv
  uv run python scripts/ingest_procurement_corp.py <path> --skip-raw   # 빠른 테스트
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import find_dotenv, load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.procurement_corp import load, normalize  # noqa: E402

load_dotenv(find_dotenv(usecwd=True))
DEFAULT_DSN = os.environ.get("DATABASE_URL", "postgresql:///eco")
KST = ZoneInfo("Asia/Seoul")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest_proc_corp")


# 광역시도 prefix → prtcptLmtRgnCd (_common.md 참조)
SIGUNGU_TO_RGN = {
    "서울": "11", "부산": "26", "대구": "27", "인천": "28", "광주": "29",
    "대전": "30", "울산": "31", "세종": "36", "경기": "41",
    "강원": "42", "충북": "43", "충남": "44", "전북": "45",
    "전남": "46", "경북": "47", "경남": "48", "제주": "50",
}
REGION_CASE_SQL = "CASE " + " ".join(
    f"WHEN addr_sigungu LIKE '{p}%%' THEN '{c}'" for p, c in SIGUNGU_TO_RGN.items()
) + " ELSE NULL END"


def _none_if_nan(v):
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def insert_raw(
    conn, df_raw: pd.DataFrame, file_name: str, fetched_at: datetime,
    batch: int = 5000,
) -> int:
    """원본(post-rename, snake_case) row를 JSONB로 적재."""
    sql = """
    INSERT INTO raw_procurement_corp (fetched_at, file_name, row_seq, row_data)
    VALUES %s
    """
    n = len(df_raw)
    inserted = 0
    with conn.cursor() as cur:
        for start in range(0, n, batch):
            chunk = df_raw.iloc[start:start + batch]
            rows = []
            for offset, rec in enumerate(chunk.to_dict("records")):
                clean = {}
                for k, v in rec.items():
                    cv = _none_if_nan(v)
                    if cv is not None and hasattr(cv, "isoformat"):
                        cv = cv.isoformat()
                    clean[k] = cv
                rows.append((fetched_at, file_name, start + offset + 1,
                             psycopg2.extras.Json(clean)))
            psycopg2.extras.execute_values(cur, sql, rows, page_size=batch)
            inserted += len(rows)
            conn.commit()
            if inserted % 50000 == 0 or inserted == n:
                logger.info("  raw progress: %d/%d", inserted, n)
    return inserted


STG_COLS = [
    "fetched_at", "brn", "branch_type", "addr_sigungu", "corp_name",
    "corp_name_normalized", "country", "is_domestic", "is_headquarter",
    "corp_size", "main_industry", "is_manufacturer",
    "main_dtil_prdct_cd", "main_dtil_prdct_nm", "g2b_registered_at",
    "female_ceo_flag", "disabled_corp_flag", "social_corp_flag",
    "sr_data_present",
]
STG_SQL = f"INSERT INTO stg_procurement_corp ({', '.join(STG_COLS)}) VALUES %s"


def insert_stg(
    conn, df_norm: pd.DataFrame, fetched_at: datetime, batch: int = 5000,
) -> int:
    """정규화 dataframe → stg_procurement_corp (TRUNCATE + INSERT)."""
    # PK 충돌 회피: (brn, branch_type, addr_sigungu) 중복 제거
    n_before = len(df_norm)
    df_norm = df_norm.drop_duplicates(
        subset=["brn", "branch_type", "addr_sigungu"], keep="first"
    ).copy()
    n_after = len(df_norm)
    if n_before != n_after:
        logger.info("PK 중복 dedupe: %d → %d", n_before, n_after)

    n = len(df_norm)
    inserted = 0
    with conn.cursor() as cur:
        cur.execute("TRUNCATE stg_procurement_corp")
        for start in range(0, n, batch):
            chunk = df_norm.iloc[start:start + batch]
            rows = []
            for rec in chunk.to_dict("records"):
                rows.append((
                    fetched_at,
                    rec["brn"],
                    rec["branch_type"],
                    _none_if_nan(rec.get("addr_sigungu")),
                    rec["corp_name"],
                    _none_if_nan(rec.get("corp_name_normalized")),
                    _none_if_nan(rec.get("country")),
                    bool(rec["is_domestic"]),
                    bool(rec["is_headquarter"]),
                    _none_if_nan(rec.get("corp_size")),
                    _none_if_nan(rec.get("main_industry")),
                    bool(rec["is_manufacturer"]),
                    _none_if_nan(rec.get("main_dtil_prdct_cd")),
                    _none_if_nan(rec.get("main_dtil_prdct_nm")),
                    _none_if_nan(rec.get("g2b_registered_at")),
                    bool(rec["female_ceo_flag"]),
                    bool(rec["disabled_corp_flag"]),
                    bool(rec["social_corp_flag"]),
                    bool(rec["sr_data_present"]),
                ))
            psycopg2.extras.execute_values(cur, STG_SQL, rows, page_size=batch)
            inserted += len(rows)
            if inserted % 50000 == 0 or inserted == n:
                logger.info("  stg progress: %d/%d", inserted, n)
    conn.commit()
    return inserted


MART_MASTER_SQL = f"""
TRUNCATE mart_company_master;
INSERT INTO mart_company_master (
    brn, corp_name, corp_name_normalized, addr_sigungu, region_code,
    corp_size, main_industry, is_manufacturer,
    main_dtil_prdct_cd, main_dtil_prdct_nm, g2b_registered_at,
    branch_count, last_synced_at
)
WITH ranked AS (
    SELECT s.*,
           ROW_NUMBER() OVER (
               PARTITION BY brn
               ORDER BY (CASE WHEN is_headquarter THEN 0 ELSE 1 END), addr_sigungu
           ) AS rn
    FROM stg_procurement_corp s
    WHERE is_domestic
), counts AS (
    SELECT brn, COUNT(*)::INTEGER AS branch_count
    FROM stg_procurement_corp
    WHERE is_domestic GROUP BY brn
)
SELECT
    r.brn, r.corp_name, r.corp_name_normalized, r.addr_sigungu,
    {REGION_CASE_SQL},
    r.corp_size, r.main_industry, r.is_manufacturer,
    r.main_dtil_prdct_cd, r.main_dtil_prdct_nm, r.g2b_registered_at,
    c.branch_count, now()
FROM ranked r JOIN counts c USING (brn)
WHERE r.rn = 1;
"""

MART_SR_SQL = """
TRUNCATE mart_company_sr;
INSERT INTO mart_company_sr (
    brn, female_ceo_flag, disabled_corp_flag, social_corp_flag,
    sr_data_present, sr_count, last_synced_at
)
WITH ranked AS (
    SELECT s.*,
           ROW_NUMBER() OVER (
               PARTITION BY brn
               ORDER BY (CASE WHEN is_headquarter THEN 0 ELSE 1 END), addr_sigungu
           ) AS rn
    FROM stg_procurement_corp s
    WHERE is_domestic
)
SELECT
    brn, female_ceo_flag, disabled_corp_flag, social_corp_flag, sr_data_present,
    (CASE WHEN female_ceo_flag THEN 1 ELSE 0 END
     + CASE WHEN disabled_corp_flag THEN 1 ELSE 0 END
     + CASE WHEN social_corp_flag THEN 1 ELSE 0 END)::SMALLINT AS sr_count,
    now()
FROM ranked WHERE rn = 1;
"""


def build_marts(conn) -> tuple[int, int]:
    with conn.cursor() as cur:
        cur.execute(MART_MASTER_SQL)
        cur.execute("SELECT COUNT(*) FROM mart_company_master")
        n_master = cur.fetchone()[0]
        cur.execute(MART_SR_SQL)
        cur.execute("SELECT COUNT(*) FROM mart_company_sr")
        n_sr = cur.fetchone()[0]
    conn.commit()
    return n_master, n_sr


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("path", help="CSV 파일 경로 (UTF-16 + tab)")
    p.add_argument("--dsn", default=DEFAULT_DSN)
    p.add_argument("--skip-raw", action="store_true",
                   help="raw_procurement_corp 적재 생략 (~1분 단축)")
    args = p.parse_args()

    csv_path = Path(args.path).expanduser().resolve()
    if not csv_path.exists():
        logger.error("파일 없음: %s", csv_path)
        return 1

    fetched_at = datetime.now(tz=KST)
    logger.info("fetched_at=%s file=%s", fetched_at.isoformat(), csv_path.name)

    logger.info("CSV 로딩 (UTF-16 + tab)...")
    df_raw = load(csv_path)
    logger.info("로딩 완료: %d rows × %d cols", *df_raw.shape)

    logger.info("정규화...")
    df_norm = normalize(df_raw)
    logger.info("정규화 완료: %d rows", len(df_norm))

    with psycopg2.connect(args.dsn) as conn:
        if not args.skip_raw:
            logger.info("raw 적재 시작...")
            n_raw = insert_raw(conn, df_raw, csv_path.name, fetched_at)
            logger.info("raw 적재 완료: %d", n_raw)
        else:
            logger.info("raw 적재 생략 (--skip-raw)")

        logger.info("stg 재구축...")
        n_stg = insert_stg(conn, df_norm, fetched_at)
        logger.info("stg 적재 완료: %d", n_stg)

        logger.info("mart 재구축...")
        n_master, n_sr = build_marts(conn)
        logger.info("mart_company_master=%d mart_company_sr=%d", n_master, n_sr)

    print()
    print("─" * 70)
    print(f"stg_procurement_corp = {n_stg:,}")
    print(f"mart_company_master  = {n_master:,}")
    print(f"mart_company_sr      = {n_sr:,}")
    print("─" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
