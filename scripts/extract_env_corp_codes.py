"""
한국환경공단 산하 본부별 dminsttCd 전수 매핑 추출.

전략: 1년치를 1개월씩 슬라이딩해서 호출 → dminsttCd/dminsttNm 짝 누적 → dedupe.

사용법:
    export G2B_SERVICE_KEY="본인_키"
    python extract_env_corp_codes.py
"""
import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from collections import defaultdict

import requests


SERVICE_KEY = os.environ.get(
    "G2B_SERVICE_KEY",
    "여기에_본인_ServiceKey_Decoding_키",
)

URL = (
    "http://apis.data.go.kr/1230000/ad/BidPublicInfoService"
    "/getBidPblancListInfoThngPPSSrch"
)


def fetch_month(bgn: str, end: str) -> list[dict]:
    """한 달치 호출 — 페이징 끝까지 돌려서 전부 수집."""
    rows = []
    page = 1
    while True:
        params = {
            "ServiceKey": SERVICE_KEY,
            "inqryDiv": "1",
            "inqryBgnDt": bgn,
            "inqryEndDt": end,
            "dminsttNm": "한국환경공단",  # 부분 일치 → 산하 본부 전부 매칭
            "pageNo": str(page),
            "numOfRows": "100",
            "type": "xml",
        }
        r = requests.get(URL, params=params, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.text)

        if root.tag == "OpenAPI_ServiceResponse":
            print(f"  ⚠️  게이트웨이 에러: {root.findtext('.//returnAuthMsg')}")
            return rows

        if root.findtext(".//resultCode") != "00":
            print(f"  ⚠️  비정상 응답: {root.findtext('.//resultMsg')}")
            return rows

        items = root.findall(".//item")
        if not items:
            break

        for it in items:
            rows.append({
                "dminsttCd": it.findtext("dminsttCd") or "",
                "dminsttNm": it.findtext("dminsttNm") or "",
            })

        total = int(root.findtext(".//totalCount") or "0")
        if page * 100 >= total:
            break
        page += 1
        time.sleep(0.1)  # rate limit 보호

    return rows


def month_windows(start: date, end: date):
    """start~end를 한 달 단위로 쪼개서 (bgn, end) 문자열 쌍 yield."""
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=30), end)
        yield (
            cur.strftime("%Y%m%d") + "0000",
            nxt.strftime("%Y%m%d") + "2359",
        )
        cur = nxt + timedelta(days=1)


def main() -> int:
    if SERVICE_KEY.startswith("여기에"):
        print("❌ ServiceKey가 설정되지 않았습니다.")
        return 1

    today = date.today()
    start = today - timedelta(days=365)  # 최근 1년

    print(f"📡 {start} ~ {today}, 한 달씩 슬라이딩 호출")
    print()

    counter = defaultdict(int)
    name_map = {}

    for bgn, end in month_windows(start, today):
        print(f"  {bgn[:8]} ~ {end[:8]} ...", end="", flush=True)
        rows = fetch_month(bgn, end)
        print(f" {len(rows)}건")
        for row in rows:
            cd = row["dminsttCd"]
            nm = row["dminsttNm"]
            if cd:
                counter[cd] += 1
                name_map[cd] = nm

    print()
    print("─" * 70)
    print(f"{'dminsttCd':<10} {'count':>6}  dminsttNm")
    print("─" * 70)
    for cd in sorted(counter.keys()):
        print(f"{cd:<10} {counter[cd]:>6}  {name_map[cd]}")
    print("─" * 70)
    print(f"총 {len(counter)}개 기관 코드 발견")

    return 0


if __name__ == "__main__":
    sys.exit(main())
