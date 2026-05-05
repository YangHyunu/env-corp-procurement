"""
raw → stg 빌드. raw_g2b_bid_notice → stg_bid_notice, raw_g2b_award → stg_award.

전략:
  - 같은 (bid_ntce_no, bid_ntce_ord, ...) PK 기준으로 가장 최근 fetched_at 1행만 사용
  - XML을 Python ET로 파싱 → 타입 정규화 (BIGINT, NUMERIC, TIMESTAMPTZ)
  - TRUNCATE + INSERT (전체 재구축)

사용:
  uv run python scripts/build_stg.py
  uv run python scripts/build_stg.py --only bid_notice
  uv run python scripts/build_stg.py --only award
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import find_dotenv, load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.g2b_common import (  # noqa: E402
    ENV_CORP_DMINSTT_CDS,
    ENV_CORP_DMINSTT_NAMES,
    normalize_brn,
    parse_dt,
    parse_openg_corp_info,
    to_float,
    to_int,
)

load_dotenv(find_dotenv(usecwd=True))
DEFAULT_DSN = os.environ.get("DATABASE_URL", "postgresql:///eco")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_stg")

ENV_SET = set(ENV_CORP_DMINSTT_CDS)


# ── 14번: stg_bid_notice ────────────────────────────────────────────────
RAW_BID_NOTICE_SQL = """
SELECT DISTINCT ON (bid_ntce_no, bid_ntce_ord)
    bid_ntce_no, bid_ntce_ord, item_xml, fetched_at
FROM raw_g2b_bid_notice
ORDER BY bid_ntce_no, bid_ntce_ord, fetched_at DESC
"""

STG_BID_NOTICE_COLS = [
    "bid_ntce_no", "bid_ntce_ord", "bid_ntce_nm",
    "dminstt_cd", "dminstt_nm", "ntce_instt_cd", "ntce_instt_nm",
    "dtil_prdct_clsfc_no", "dtil_prdct_clsfc_no_nm",
    "presmpt_prce", "asign_bdgt_amt",
    "bid_ntce_dt", "openg_dt", "bid_clse_dt",
    "cntrct_cncls_mthd_nm", "is_env_corp", "fetched_at",
]
STG_BID_NOTICE_INSERT = (
    f"INSERT INTO stg_bid_notice ({', '.join(STG_BID_NOTICE_COLS)}) VALUES %s"
)


def _txt(it: ET.Element, tag: str) -> str | None:
    v = it.findtext(tag)
    if v is None:
        return None
    v = v.strip()
    return v or None


def parse_bid_notice(xml_str: str, fetched_at: datetime) -> tuple | None:
    it = ET.fromstring(xml_str)
    bid_ntce_no = _txt(it, "bidNtceNo")
    bid_ntce_ord = _txt(it, "bidNtceOrd")
    if not bid_ntce_no or not bid_ntce_ord:
        return None

    dminstt_cd = _txt(it, "dminsttCd")
    return (
        bid_ntce_no,
        bid_ntce_ord,
        _txt(it, "bidNtceNm") or "",   # NOT NULL
        dminstt_cd,
        _txt(it, "dminsttNm"),
        _txt(it, "ntceInsttCd"),
        _txt(it, "ntceInsttNm"),
        _txt(it, "dtilPrdctClsfcNo"),
        _txt(it, "dtilPrdctClsfcNoNm"),
        to_int(_txt(it, "presmptPrce")),
        to_int(_txt(it, "asignBdgtAmt")),
        parse_dt(_txt(it, "bidNtceDt")),
        parse_dt(_txt(it, "opengDt")),
        parse_dt(_txt(it, "bidClseDt")),
        _txt(it, "cntrctCnclsMthdNm"),
        dminstt_cd in ENV_SET,
        fetched_at,
    )


def build_bid_notice(conn) -> int:
    rows = []
    with conn.cursor(name="raw_bid_cur") as cur:
        cur.execute(RAW_BID_NOTICE_SQL)
        for _no, _ord, xml_str, fetched_at in cur:
            try:
                row = parse_bid_notice(xml_str, fetched_at)
            except ET.ParseError as e:
                logger.error("XML parse error on %s/%s: %s", _no, _ord, e)
                continue
            if row:
                rows.append(row)

    n = len(rows)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE stg_bid_notice")
        for start in range(0, n, 5000):
            psycopg2.extras.execute_values(
                cur, STG_BID_NOTICE_INSERT, rows[start:start + 5000], page_size=5000
            )
    conn.commit()
    return n


# ── 1번: stg_award ───────────────────────────────────────────────────────
RAW_AWARD_SQL = """
SELECT DISTINCT ON (bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no)
    item_xml, fetched_at
FROM raw_g2b_award
ORDER BY bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no, fetched_at DESC
"""

STG_AWARD_COLS = [
    "bid_ntce_no", "bid_ntce_ord", "bid_clsfc_no", "rbid_no",
    "bid_ntce_nm",
    "bidwinnr_nm", "bidwinnr_brn", "bidwinnr_ceo_nm", "bidwinnr_adrs",
    "sucsfbid_amt", "sucsfbid_rate", "prtcpt_cnum",
    "rl_openg_dt", "fnl_sucsf_date",
    "dminstt_cd", "dminstt_nm", "rgst_dt", "fetched_at",
]
STG_AWARD_INSERT = (
    f"INSERT INTO stg_award ({', '.join(STG_AWARD_COLS)}) VALUES %s"
)


def parse_award(xml_str: str, fetched_at: datetime) -> tuple | None:
    it = ET.fromstring(xml_str)

    bid_ntce_no = _txt(it, "bidNtceNo")
    bid_ntce_ord = _txt(it, "bidNtceOrd")
    bid_clsfc_no = _txt(it, "bidClsfcNo")
    rbid_no = _txt(it, "rbidNo")
    if not all((bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no)):
        return None

    brn_raw = _txt(it, "bidwinnrBizno")
    brn = normalize_brn(brn_raw)
    bidwinnr_nm = _txt(it, "bidwinnrNm") or ""
    if not brn or not bidwinnr_nm:
        # NOT NULL 위반 방지
        return None

    rgst_dt = parse_dt(_txt(it, "rgstDt"))
    if rgst_dt is None:
        return None

    fnl_date_raw = _txt(it, "fnlSucsfDate")
    fnl_date: date | None = None
    if fnl_date_raw:
        try:
            fnl_date = datetime.strptime(fnl_date_raw, "%Y-%m-%d").date()
        except ValueError:
            fnl_date = None

    return (
        bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no,
        _txt(it, "bidNtceNm"),
        bidwinnr_nm, brn, _txt(it, "bidwinnrCeoNm"), _txt(it, "bidwinnrAdrs"),
        to_int(_txt(it, "sucsfbidAmt")),
        to_float(_txt(it, "sucsfbidRate")),
        to_int(_txt(it, "prtcptCnum")),
        parse_dt(_txt(it, "rlOpengDt")),
        fnl_date,
        _txt(it, "dminsttCd"),
        _txt(it, "dminsttNm"),
        rgst_dt,
        fetched_at,
    )


def build_award(conn) -> int:
    rows = []
    skipped = 0
    with conn.cursor(name="raw_award_cur") as cur:
        cur.execute(RAW_AWARD_SQL)
        for xml_str, fetched_at in cur:
            try:
                row = parse_award(xml_str, fetched_at)
            except ET.ParseError as e:
                logger.error("XML parse error: %s", e)
                continue
            if row:
                rows.append(row)
            else:
                skipped += 1

    if skipped:
        logger.info("award skipped (NOT NULL 위반/누락): %d", skipped)

    n = len(rows)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE stg_award")
        for start in range(0, n, 5000):
            psycopg2.extras.execute_values(
                cur, STG_AWARD_INSERT, rows[start:start + 5000], page_size=5000
            )
    conn.commit()
    return n


# ── 5번: stg_opening_result ─────────────────────────────────────────────
RAW_OPENING_SQL = """
SELECT DISTINCT ON (bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no)
    item_xml, fetched_at
FROM raw_g2b_opening
ORDER BY bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no, fetched_at DESC
"""

STG_OPENING_COLS = [
    "bid_ntce_no", "bid_ntce_ord", "bid_clsfc_no", "rbid_no",
    "bid_ntce_nm", "openg_dt", "prtcpt_cnum",
    "progrs_div_cd_nm", "rsrvtn_prce_file_yn",
    "openg_case", "winner_name", "winner_brn", "winner_ceo_nm",
    "bid_amount", "bid_rate",
    "dminstt_cd", "dminstt_nm", "inpt_dt", "fetched_at",
]
STG_OPENING_INSERT = (
    f"INSERT INTO stg_opening_result ({', '.join(STG_OPENING_COLS)}) VALUES %s"
)


def parse_opening(xml_str: str, fetched_at: datetime) -> tuple | None:
    it = ET.fromstring(xml_str)

    bid_ntce_no = _txt(it, "bidNtceNo")
    bid_ntce_ord = _txt(it, "bidNtceOrd")
    bid_clsfc_no = _txt(it, "bidClsfcNo")
    rbid_no = _txt(it, "rbidNo")
    if not all((bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no)):
        return None

    progrs = _txt(it, "progrsDivCdNm")
    if not progrs:
        return None  # NOT NULL

    parsed = parse_openg_corp_info(_txt(it, "opengCorpInfo"))

    return (
        bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no,
        _txt(it, "bidNtceNm"),
        parse_dt(_txt(it, "opengDt")),
        to_int(_txt(it, "prtcptCnum")),
        progrs,
        _txt(it, "rsrvtnPrceFileExistnceYn"),
        parsed["case"],
        parsed.get("winner_name"),
        parsed.get("brn"),
        parsed.get("ceo_name"),
        parsed.get("bid_amount"),
        parsed.get("bid_rate"),
        _txt(it, "dminsttCd"),
        _txt(it, "dminsttNm"),
        parse_dt(_txt(it, "inptDt")),
        fetched_at,
    )


def build_opening(conn) -> int:
    rows = []
    skipped = 0
    with conn.cursor(name="raw_opening_cur") as cur:
        cur.execute(RAW_OPENING_SQL)
        for xml_str, fetched_at in cur:
            try:
                row = parse_opening(xml_str, fetched_at)
            except ET.ParseError as e:
                logger.error("XML parse error: %s", e)
                continue
            if row:
                rows.append(row)
            else:
                skipped += 1

    if skipped:
        logger.info("opening skipped (PK/progrs 누락): %d", skipped)

    n = len(rows)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE stg_opening_result")
        for start in range(0, n, 5000):
            psycopg2.extras.execute_values(
                cur, STG_OPENING_INSERT, rows[start:start + 5000], page_size=5000
            )
    conn.commit()
    return n


# ── 9번: stg_prepar_price + mart_bid_prepar ────────────────────────────
RAW_PREPAR_SQL = """
SELECT DISTINCT ON (bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no, prce_sno)
    item_xml, fetched_at
FROM raw_g2b_prepar
ORDER BY bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no, prce_sno, fetched_at DESC
"""

STG_PREPAR_COLS = [
    "bid_ntce_no", "bid_ntce_ord", "bid_clsfc_no", "rbid_no", "prce_sno",
    "bsis_plnprc", "drwt_yn", "drwt_num",
    "plnprc", "bssamt", "bssamt_bss_up_num",
    "compno_mkng_dt", "rl_openg_dt", "fetched_at",
]
STG_PREPAR_INSERT = (
    f"INSERT INTO stg_prepar_price ({', '.join(STG_PREPAR_COLS)}) VALUES %s"
)


def parse_prepar(xml_str: str, fetched_at: datetime) -> tuple | None:
    it = ET.fromstring(xml_str)

    bid_ntce_no = _txt(it, "bidNtceNo")
    bid_ntce_ord = _txt(it, "bidNtceOrd")
    bid_clsfc_no = _txt(it, "bidClsfcNo")
    rbid_no = _txt(it, "rbidNo")
    prce_sno = to_int(_txt(it, "compnoRsrvtnPrceSno"))
    if not all((bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no)) or prce_sno is None:
        return None

    return (
        bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no, prce_sno,
        to_int(_txt(it, "bsisPlnprc")),
        _txt(it, "drwtYn"),
        to_int(_txt(it, "drwtNum")),
        to_int(_txt(it, "plnprc")),
        to_int(_txt(it, "bssamt")),
        to_int(_txt(it, "bssamtBssUpNum")),
        parse_dt(_txt(it, "compnoRsrvtnPrceMkngDt")),
        parse_dt(_txt(it, "rlOpengDt")),
        fetched_at,
    )


def build_prepar_stg(conn) -> int:
    rows = []
    skipped = 0
    with conn.cursor(name="raw_prepar_cur") as cur:
        cur.execute(RAW_PREPAR_SQL)
        for xml_str, fetched_at in cur:
            try:
                row = parse_prepar(xml_str, fetched_at)
            except ET.ParseError as e:
                logger.error("XML parse error: %s", e)
                continue
            if row:
                rows.append(row)
            else:
                skipped += 1
    if skipped:
        logger.info("prepar skipped (PK 누락): %d", skipped)

    n = len(rows)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE stg_prepar_price")
        for start in range(0, n, 5000):
            psycopg2.extras.execute_values(
                cur, STG_PREPAR_INSERT, rows[start:start + 5000], page_size=5000
            )
    conn.commit()
    return n


# stg → mart 공고 단위 집계
MART_PREPAR_SQL = """
TRUNCATE mart_bid_prepar;
INSERT INTO mart_bid_prepar (
    bid_ntce_no, bid_ntce_ord,
    plnprc, bssamt, bssamt_bss_up_num,
    n_prces, n_drawn,
    bsis_min, bsis_max, bsis_mean, bsis_std, bsis_range_pct,
    drawn_snos, compno_mkng_dt
)
SELECT
    bid_ntce_no, bid_ntce_ord,
    MAX(plnprc), MAX(bssamt), MAX(bssamt_bss_up_num),
    COUNT(*) AS n_prces,
    SUM(CASE WHEN drwt_yn='Y' THEN 1 ELSE 0 END) AS n_drawn,
    MIN(bsis_plnprc), MAX(bsis_plnprc),
    AVG(bsis_plnprc)::numeric(20,2),
    STDDEV(bsis_plnprc)::numeric(20,2),
    CASE WHEN AVG(bsis_plnprc) > 0
         THEN ((MAX(bsis_plnprc) - MIN(bsis_plnprc))::numeric / AVG(bsis_plnprc) * 100)::numeric(6,3)
         ELSE NULL END,
    ARRAY_AGG(prce_sno ORDER BY prce_sno) FILTER (WHERE drwt_yn='Y'),
    MAX(compno_mkng_dt)
FROM stg_prepar_price
GROUP BY bid_ntce_no, bid_ntce_ord
"""


def build_prepar_mart(conn) -> int:
    with conn.cursor() as cur:
        cur.execute(MART_PREPAR_SQL)
        n = cur.rowcount
    conn.commit()
    return n


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--only", choices=["bid_notice", "award", "opening", "prepar"], default=None)
    p.add_argument("--dsn", default=DEFAULT_DSN)
    args = p.parse_args()

    with psycopg2.connect(args.dsn) as conn:
        if args.only in (None, "bid_notice"):
            logger.info("build stg_bid_notice...")
            n = build_bid_notice(conn)
            logger.info("stg_bid_notice: %d rows", n)

        if args.only in (None, "award"):
            logger.info("build stg_award...")
            n = build_award(conn)
            logger.info("stg_award: %d rows", n)

        if args.only in (None, "opening"):
            logger.info("build stg_opening_result...")
            n = build_opening(conn)
            logger.info("stg_opening_result: %d rows", n)

        if args.only in (None, "prepar"):
            logger.info("build stg_prepar_price...")
            n = build_prepar_stg(conn)
            logger.info("stg_prepar_price: %d rows", n)
            logger.info("build mart_bid_prepar...")
            n = build_prepar_mart(conn)
            logger.info("mart_bid_prepar: %d rows", n)

    return 0


if __name__ == "__main__":
    sys.exit(main())
