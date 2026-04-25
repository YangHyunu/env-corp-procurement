"""
1번 API 진단 — raw_g2b_bid_notice의 distinct bidNtceNo로 BRN 추출 시도.

목적:
  - 환경공단 공고 중 몇 %가 실제 낙찰 결과 보유(=1번 응답 hit)인지
  - 유찰/진행중 비율 추정
  - bidwinnrBizno 결측 여부 + 핵심 필드 결측률
  - DB는 read-only (raw_g2b_bid_notice 조회만)

사용:
  uv run python scripts/probe_award.py
"""
from __future__ import annotations

import os
import sys
import time
from collections import Counter
from pathlib import Path

import psycopg2
from dotenv import find_dotenv, load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.g2b_common import G2BApiError, call, make_session  # noqa: E402

load_dotenv(find_dotenv(usecwd=True))

DSN = os.environ.get("DATABASE_URL", "postgresql:///eco")
OPERATION = "as/ScsbidInfoService/getScsbidListSttusThng"

FIELDS = [
    "bidNtceNo", "bidNtceOrd", "bidClsfcNo", "rbidNo", "ntceDivCd", "bidNtceNm",
    "bidwinnrNm", "bidwinnrBizno", "bidwinnrCeoNm", "bidwinnrAdrs", "bidwinnrTelNo",
    "prtcptCnum", "sucsfbidAmt", "sucsfbidRate",
    "rlOpengDt", "fnlSucsfDate", "fnlSucsfCorpOfcl",
    "dminsttCd", "dminsttNm", "rgstDt",
]


def fetch_bid_ntce_nos() -> list[str]:
    """가장 최근 fetched_at 기준 distinct bidNtceNo 목록."""
    sql = """
    SELECT DISTINCT bid_ntce_no
    FROM raw_g2b_bid_notice
    ORDER BY bid_ntce_no
    """
    with psycopg2.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return [row[0] for row in cur.fetchall()]


def main() -> int:
    bids = fetch_bid_ntce_nos()
    if not bids:
        print("⚠️ raw_g2b_bid_notice 비어있음. 14번 ingest 먼저.")
        return 1

    print(f"📡 1번 API 진단 — {len(bids)}개 bidNtceNo (inqryDiv=4)")
    print()

    session = make_session()
    hit = 0
    miss = 0
    award_count = 0
    field_missing: Counter[str] = Counter()
    field_seen: Counter[str] = Counter()
    sample_first: dict | None = None
    miss_examples: list[str] = []

    for i, no in enumerate(bids, 1):
        params = {
            "inqryDiv": "4",
            "bidNtceNo": no,
            "pageNo": "1",
            "numOfRows": "999",
            "type": "xml",
        }
        try:
            root = call(OPERATION, params, session=session)
        except G2BApiError as e:
            print(f"❌ {no}: {e}")
            return 1

        total = int(root.findtext(".//totalCount") or "0")
        items = root.findall(".//item")

        if total > 0 and items:
            hit += 1
            award_count += len(items)
            for it in items:
                if sample_first is None:
                    sample_first = {f: it.findtext(f) for f in FIELDS}
                for f in FIELDS:
                    v = it.findtext(f)
                    if v is None or not str(v).strip():
                        field_missing[f] += 1
                    else:
                        field_seen[f] += 1
        else:
            miss += 1
            if len(miss_examples) < 5:
                miss_examples.append(no)

        if i % 10 == 0:
            print(f"  진행 {i}/{len(bids)}  hit={hit} miss={miss}")
        time.sleep(0.1)

    # 결과
    print()
    print("─" * 70)
    print(f"hit  (낙찰 있음)    : {hit:>3d}/{len(bids)} ({hit / len(bids) * 100:5.1f}%)")
    print(f"miss (totalCount=0): {miss:>3d}/{len(bids)} ({miss / len(bids) * 100:5.1f}%)")
    print(f"총 award 행        : {award_count} (hit 평균 {award_count / max(hit, 1):.2f}건/공고)")

    if miss_examples:
        print(f"miss 예시         : {', '.join(miss_examples)}")

    if award_count == 0:
        print()
        print("⚠️  award 0건. 30일 모집단으론 부족 가능성 — 백필 또는 더 과거 윈도우 필요.")
        return 0

    print()
    print("─" * 70)
    print(f"필드 결측률 (n={award_count})")
    print("─" * 70)
    for f in FIELDS:
        m = field_missing.get(f, 0)
        s = field_seen.get(f, 0)
        denom = m + s
        if denom == 0:
            pct = 0.0
            flag = "  (필드 자체 없음)"
        else:
            pct = m / denom * 100
            if pct > 50:
                flag = "  ⚠️ 절반 초과"
            elif m == 0:
                flag = "  ✅ 결측 0"
            else:
                flag = ""
        print(f"  {f:<22} present={s:>4d} missing={m:>4d} {pct:>5.1f}%{flag}")

    if sample_first:
        print()
        print("─" * 70)
        print("샘플 1건:")
        for k, v in sample_first.items():
            v_disp = "(null)" if v is None else str(v)[:90]
            print(f"  {k:<22} {v_disp}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
