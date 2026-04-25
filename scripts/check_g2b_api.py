"""
나라장터 OpenAPI 빠른 진단 스크립트
- 14번 API (getBidPblancListInfoThngPPSSrch, 입찰공고 조회) 호출
- 2026-04-01 하루치 공고 조회 → API가 정상 동작하는지만 확인

사용법:
    1. 아래 SERVICE_KEY에 본인 키 직접 입력
       또는 환경변수 G2B_SERVICE_KEY 설정 후 실행
    2. python check_g2b_api.py

기대 결과:
    ✅ API 정상 — N건 조회됨    → 통과
    ⚠️ 데이터 0건                → 기간 더 과거로 변경
    ❌ 게이트웨이 에러            → ServiceKey 또는 활용신청 문제
"""
import os
import sys
import xml.etree.ElementTree as ET

import requests


# ────────────────────────────────────────────────────────────
# 설정
# ────────────────────────────────────────────────────────────
SERVICE_KEY = os.environ.get(
    "G2B_SERVICE_KEY",
    "여기에_본인_ServiceKey_Decoding_키",  # 환경변수 안 쓰면 직접 여기에 입력
)

URL = (
    "http://apis.data.go.kr/1230000/ad/BidPublicInfoService"
    "/getBidPblancListInfoThngPPSSrch"
)

PARAMS = {
    "ServiceKey": SERVICE_KEY,
    "inqryDiv": "1",              # 1 = 공고게시일시 기준
    "inqryBgnDt": "202604010000", # 2026-04-01 00:00
    "inqryEndDt": "202604012359", # 2026-04-01 23:59
    "pageNo": "1",
    "numOfRows": "10",
    "type": "xml",
}


def main() -> int:
    # 1. ServiceKey 체크
    if SERVICE_KEY.startswith("여기에"):
        print("❌ ServiceKey가 설정되지 않았습니다.")
        print("   - 코드 상단 SERVICE_KEY를 직접 입력하거나")
        print("   - 환경변수 G2B_SERVICE_KEY 를 설정하세요.")
        return 1

    print(f"📡 GET {URL}")
    print(f"   기간: {PARAMS['inqryBgnDt']} ~ {PARAMS['inqryEndDt']}")
    print()

    # 2. 호출
    try:
        r = requests.get(URL, params=PARAMS, timeout=10)
    except requests.RequestException as e:
        print(f"❌ 요청 실패: {e}")
        return 1

    print(f"HTTP {r.status_code}")
    print(f"실제 호출 URL: {r.url}")
    print("─" * 60)
    print(r.text[:2000])
    print("─" * 60)

    if r.status_code != 200:
        print(f"❌ HTTP 에러 (상태코드 {r.status_code})")
        return 1

    # 3. XML 파싱
    try:
        root = ET.fromstring(r.text)
    except ET.ParseError as e:
        print(f"⚠️  XML 파싱 실패: {e}")
        return 1

    # 4. 게이트웨이 에러 감지 (ServiceKey/활용신청 문제일 때 옴)
    if root.tag == "OpenAPI_ServiceResponse":
        auth_msg = root.findtext(".//returnAuthMsg") or "(없음)"
        reason = root.findtext(".//returnReasonCode") or "(없음)"
        print("❌ 게이트웨이 에러 (인증/권한 문제)")
        print(f"   returnAuthMsg    : {auth_msg}")
        print(f"   returnReasonCode : {reason}")
        return 1

    # 5. 정상 응답 파싱
    result_code = root.findtext(".//resultCode")
    result_msg = root.findtext(".//resultMsg")
    total_count = root.findtext(".//totalCount")

    print(f"resultCode : {result_code}")
    print(f"resultMsg  : {result_msg}")
    print(f"totalCount : {total_count}")
    print()

    if result_code != "00":
        print("⚠️  정상 응답이 아닙니다.")
        return 1

    if total_count == "0":
        print("⚠️  데이터 0건 — 기간을 더 과거로 바꿔서 재시도해 보세요.")
        print("   예: inqryBgnDt='202507010000', inqryEndDt='202507012359'")
        return 0

    print(f"✅ API 정상 — {total_count}건 조회됨")
    return 0


if __name__ == "__main__":
    sys.exit(main())
