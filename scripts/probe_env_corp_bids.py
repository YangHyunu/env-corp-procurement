"""
14번 API 진단 — 한국환경공단 10개 dminsttCd, 최근 30일치.

목적:
  - 환경공단 한정 필터로 실제 응답 totalCount 확인
  - 샘플 100건의 키 필드 결측률 측정 (적재 스키마/파서 결정에 사용)
  - DB 미사용. 콘솔 출력만.

사용:
  uv run python scripts/probe_env_corp_bids.py
"""
from __future__ import annotations

import sys
import time
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

# repo root을 import path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.g2b_common import (  # noqa: E402
    ENV_CORP_DMINSTT_CDS,
    ENV_CORP_DMINSTT_NAMES,
    G2BApiError,
    call,
    make_session,
)

OPERATION = "ad/BidPublicInfoService/getBidPblancListInfoThngPPSSrch"

# 최근 30일 윈도우 (1개월 한도 안쪽)
END = date.today()
BGN = END - timedelta(days=30)
BGN_STR = BGN.strftime("%Y%m%d") + "0000"
END_STR = END.strftime("%Y%m%d") + "2359"

# 결측률을 측정할 핵심 필드
FIELDS = [
    "bidNtceNo", "bidNtceOrd", "bidNtceNm",
    "dminsttCd", "dminsttNm",
    "ntceInsttCd", "ntceInsttNm",
    "dtilPrdctClsfcNo", "dtilPrdctClsfcNoNm",
    "presmptPrce", "asignBdgtAmt",
    "bidNtceDt", "opengDt", "bidClseDt",
    "cntrctCnclsMthdNm",
    "bidwinnrNm", "bidwinnrBizno",  # 14번에 들어있는지 확인용
]


def probe_one(dminstt_cd: str, name: str, session) -> dict:
    """단일 기관: totalCount + page 1(100건) 샘플."""
    params = {
        "inqryDiv": "1",
        "inqryBgnDt": BGN_STR,
        "inqryEndDt": END_STR,
        "dminsttCd": dminstt_cd,
        "pageNo": "1",
        "numOfRows": "100",
        "type": "xml",
    }
    root = call(OPERATION, params, session=session)
    total = int(root.findtext(".//totalCount") or "0")
    items = root.findall(".//item")

    missing = Counter()
    seen_fields = Counter()
    sample_first = None
    for it in items:
        if sample_first is None:
            sample_first = {f: it.findtext(f) for f in FIELDS}
        for f in FIELDS:
            v = it.findtext(f)
            if v is None or not str(v).strip():
                missing[f] += 1
            else:
                seen_fields[f] += 1

    return {
        "name": name,
        "total": total,
        "sampled": len(items),
        "missing": dict(missing),
        "seen": dict(seen_fields),
        "sample_first": sample_first or {},
    }


def main() -> int:
    print(f"📡 14번 API 진단 — 한국환경공단 10개 dminsttCd")
    print(f"   기간: {BGN_STR} ~ {END_STR} (최근 30일)")
    print()

    session = make_session()
    rows: list[tuple[str, dict]] = []

    print(f"{'dminsttCd':<10} {'name':<32} {'total':>6} {'sampled':>8}")
    print("-" * 60)
    for cd in ENV_CORP_DMINSTT_CDS:
        name = ENV_CORP_DMINSTT_NAMES[cd]
        try:
            r = probe_one(cd, name, session)
        except G2BApiError as e:
            print(f"❌ G2BApiError on {cd} ({name}): {e}")
            return 1
        except Exception as e:
            print(f"❌ {type(e).__name__} on {cd} ({name}): {e}")
            return 1
        rows.append((cd, r))
        print(f"{cd:<10} {name[:30]:<32} {r['total']:>6d} {r['sampled']:>8d}")
        time.sleep(0.15)  # rate limit 보호

    total_collected = sum(r["total"] for _, r in rows)
    total_sampled = sum(r["sampled"] for _, r in rows)
    print()
    print(f"합계: totalCount={total_collected}, sampled={total_sampled}")

    if total_sampled == 0:
        print("⚠️  샘플 0건. 기간을 더 과거로 바꿔서 재시도하세요.")
        return 0

    # 필드 결측률 합산
    print()
    print("─" * 70)
    print(f"필드 결측률 (샘플 합산, n={total_sampled})")
    print("─" * 70)
    agg_missing = Counter()
    agg_seen = Counter()
    for _, r in rows:
        for f, n in r["missing"].items():
            agg_missing[f] += n
        for f, n in r["seen"].items():
            agg_seen[f] += n

    for f in FIELDS:
        m = agg_missing.get(f, 0)
        s = agg_seen.get(f, 0)
        denom = m + s
        if denom == 0:
            pct_missing = 0.0
        else:
            pct_missing = m / denom * 100
        flag = ""
        if denom == 0:
            flag = "  (필드 자체 없음)"
        elif pct_missing > 50:
            flag = "  ⚠️ 절반 초과 결측"
        elif m == 0:
            flag = "  ✅ 결측 0"
        print(f"  {f:<22} present={s:>4d}  missing={m:>4d}  {pct_missing:>5.1f}%{flag}")

    # 첫 비어있지 않은 응답의 sample 1건 출력
    print()
    print("─" * 70)
    for _, r in rows:
        if r["sample_first"]:
            print(f"샘플 1건 ({r['name']}):")
            for k, v in r["sample_first"].items():
                v_disp = "(null)" if v is None else str(v)[:90]
                print(f"  {k:<22} {v_disp}")
            break

    return 0


if __name__ == "__main__":
    sys.exit(main())
