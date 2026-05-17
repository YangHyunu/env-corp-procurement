"""
g2b_common.py — 나라장터 OpenAPI 공통 유틸.

이 모듈을 import 하면 자동으로 같은 폴더의 .env 파일이 로드되어
G2B_SERVICE_KEY 환경변수를 사용할 수 있게 됩니다.
"""
from __future__ import annotations

import os
import re
import time
import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterator
from zoneinfo import ZoneInfo

import requests
from dotenv import find_dotenv, load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ── 환경변수 로드 (CWD 또는 상위 디렉토리에서 .env 탐색) ──
load_dotenv(find_dotenv(usecwd=True))

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")


# ── 환경 ────────────────────────────────────────────────
# G2B 키는 ingest 호출 시점에만 필요 (운영 API 부팅에는 불필요).
# module-level 강제 체크 X — make_g2b_request 안에서 lazy 확인.
def _get_service_key() -> str:
    key = os.environ.get("G2B_SERVICE_KEY")
    if not key:
        raise RuntimeError(
            "G2B_SERVICE_KEY 환경변수가 설정되지 않았습니다.\n"
            "로컬: .env 에 G2B_SERVICE_KEY=발급받은_Decoding_키\n"
            "Railway/Render: Variables 탭에 동일 이름으로 추가"
        )
    return key

BASE_URL = "http://apis.data.go.kr/1230000"


# ── 도메인 상수: 한국환경공단 dminsttCd 10개 ───────────
ENV_CORP_DMINSTT_CDS: list[str] = [
    "B552584",  # 본사
    "Z008653",  # 수도권서부환경본부
    "Z004865",  # 수도권동부환경본부
    "Z018993",  # 충청권환경본부
    "Z004863",  # 부산울산경남환경본부
    "Z003477",  # 대구경북환경본부
    "Z004864",  # 광주전남제주환경본부
    "Z042470",  # 강원환경본부
    "D266078",  # 국가물산업클러스터사업단
    "Z042433",  # 전북환경본부
]

ENV_CORP_DMINSTT_NAMES: dict[str, str] = {
    "B552584": "한국환경공단",
    "Z008653": "한국환경공단 수도권서부환경본부",
    "Z004865": "한국환경공단 수도권동부환경본부",
    "Z018993": "한국환경공단 충청권환경본부",
    "Z004863": "한국환경공단 부산울산경남환경본부",
    "Z003477": "한국환경공단 대구경북환경본부",
    "Z004864": "한국환경공단 광주전남제주환경본부",
    "Z042470": "한국환경공단 강원환경본부",
    "D266078": "한국환경공단 국가물산업클러스터사업단",
    "Z042433": "한국환경공단 전북환경본부",
}


# ── 환경 도메인 확장 (Tier 1) — 풀 확장용 ─────────────
# 14번 API dminsttNm 검색으로 추출 (수자원공사 / 광역상수도 / 환경부 산하).
# 같은 prefix4 (펌프/약품/계측기 등) 발주가 도메인적으로 유사 — 추천 풀 두께 확장.
ENV_DOMAIN_DMINSTT_CDS: list[str] = [
    # 한국수자원공사 (K-water) — 본부/사업단
    "D259074",  # 그린인프라부문 도시본부
    "Z000497",  # 한강경영처
    "D259089",  # 강원수열사업단
    "D259304",  # 낙동강유역본부 낙동강동부사업단
    "D259678",  # 낙동강유역본부 낙동강남부사업단
    "D259548",  # 한강유역본부 한강동부사업단
    # 광역시 상수도사업본부 (본부급)
    "6260095",  # 부산광역시 상수도사업본부
    "6260099",  # 부산광역시 상수도사업본부 시설관리사업소
    "6270221",  # 대구광역시 상수도사업본부
    "6310062",  # 울산광역시 상수도사업본부
    # 기후에너지환경부 + 산하
    "1482021",  # 국립환경과학원
    "1482041",  # 국립생물자원관
    "1480347",  # 환경부 한강유역환경청
    "1482027",  # 낙동강유역환경청
    "1482029",  # 영산강유역환경청
    "1482030",  # 원주지방환경청
    "1482032",  # 전북지방환경청
    "1482034",  # 한강홍수통제소
    "1482035",  # 낙동강홍수통제소
    "1482036",  # 금강홍수통제소
    "1482037",  # 영산강홍수통제소
    "1482022",  # 국립환경인재개발원
    "1482025",  # 국립야생동물질병관리원
    "1482241",  # 국립환경과학원 낙동강물환경센터
    "1482309",  # 국립환경과학원 영산강물환경센터
    "1481185",  # 국립환경과학원 한강통합물환경센터
]


def agency_tier_for(dminstt_cd: str) -> str:
    """dminstt_cd → 'env_corp' | 'env_domain' | 'other'."""
    if dminstt_cd in ENV_CORP_DMINSTT_CDS:
        return "env_corp"
    if dminstt_cd in ENV_DOMAIN_DMINSTT_CDS:
        return "env_domain"
    return "other"


# ── HTTP 세션 (재시도 내장) ─────────────────────────────
def make_session(
    total_retries: int = 5,
    backoff_factor: float = 1.0,
) -> requests.Session:
    """재시도·백오프가 적용된 requests.Session.

    - 5xx, ConnectionError, ReadTimeout 만 재시도
    - 4xx, 게이트웨이 에러는 재시도하지 않음
    """
    session = requests.Session()
    retry = Retry(
        total=total_retries,
        backoff_factor=backoff_factor,  # 1, 2, 4, 8, 16초
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# ── 호출 ────────────────────────────────────────────────
class G2BApiError(Exception):
    """게이트웨이 에러 또는 resultCode != '00'."""


def call(
    operation_path: str,
    params: dict,
    session: requests.Session | None = None,
    timeout: tuple[int, int] = (10, 60),
) -> ET.Element:
    """G2B API 호출 → 정상이면 root <response> Element 반환.

    Args:
        operation_path: 예) "ad/BidPublicInfoService/getBidPblancListInfoThngPPSSrch"
        params: ServiceKey 제외한 파라미터들
        session: None이면 기본 세션 생성
        timeout: (connect, read) — 기본 (10, 60)

    Raises:
        G2BApiError: 게이트웨이 에러 또는 resultCode != '00'
        requests.HTTPError: HTTP status가 비정상
    """
    session = session or make_session()
    url = f"{BASE_URL}/{operation_path}"
    full_params = {"ServiceKey": _get_service_key(), **params}

    r = session.get(url, params=full_params, timeout=timeout)
    r.raise_for_status()

    root = ET.fromstring(r.text)

    # 게이트웨이 에러 (인증·트래픽·파라미터 오류)
    if root.tag == "OpenAPI_ServiceResponse":
        auth = root.findtext(".//returnAuthMsg") or "(none)"
        reason = root.findtext(".//returnReasonCode") or "(none)"
        raise G2BApiError(f"Gateway error: {auth} (code={reason})")

    # 정상 응답 내 에러
    code = root.findtext(".//resultCode")
    if code != "00":
        msg = root.findtext(".//resultMsg")
        raise G2BApiError(f"resultCode={code}, msg={msg}")

    return root


# ── 페이징 ─────────────────────────────────────────────
def paginate(
    operation_path: str,
    params: dict,
    page_size: int = 100,
    session: requests.Session | None = None,
    sleep_sec: float = 0.1,
) -> Iterator[ET.Element]:
    """페이징 끝까지 돌면서 <item> Element를 yield."""
    session = session or make_session()
    page = 1
    while True:
        p = {
            **params,
            "pageNo": str(page),
            "numOfRows": str(page_size),
            "type": "xml",
        }
        root = call(operation_path, p, session=session)

        items = root.findall(".//item")
        for it in items:
            yield it

        total = int(root.findtext(".//totalCount") or "0")
        if not items or page * page_size >= total:
            break
        page += 1
        time.sleep(sleep_sec)


# ── 윈도우 분할 ────────────────────────────────────────
def month_windows(
    start: date,
    end: date,
    days: int = 30,
) -> Iterator[tuple[str, str]]:
    """1개월 윈도우 제약 회피용 (bgn, end) 12자리 문자열 쌍 yield.

    예: (2024-01-01, 2024-04-30) →
        ("202401010000", "202401312359"),
        ("202402010000", "202403022359"), ...
    """
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=days), end)
        yield (
            cur.strftime("%Y%m%d") + "0000",
            nxt.strftime("%Y%m%d") + "2359",
        )
        cur = nxt + timedelta(days=1)


# ── 정규화 ─────────────────────────────────────────────
def normalize_brn(s: str | None) -> str | None:
    """사업자등록번호 정규화.

    - 국내: 하이픈 제거 후 10자리 숫자 → 그대로 반환
    - 국외: 'F' + 9자리 = 10자리 → 그대로 반환
    - 그 외: None
    """
    if not s:
        return None
    s = str(s).strip()
    if s.startswith("F") and len(s) == 10:
        return s
    digits = re.sub(r"\D", "", s)
    return digits if len(digits) == 10 else None


def normalize_corp_name(s: str | None) -> str | None:
    """업체명 정규화: (주)/주식회사/(유)/유한회사 통일, 공백 정리."""
    if not s:
        return None
    s = str(s).strip()
    s = re.sub(r"\(주\)|주식회사", "", s)
    s = re.sub(r"\(유\)|유한회사", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def parse_dt(s: str | None) -> datetime | None:
    """G2B 응답의 3가지 시간 포맷 모두 파싱 (KST tzinfo 부여)."""
    if not s or not str(s).strip():
        return None
    s = str(s).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=KST)
        except ValueError:
            continue
    logger.warning("Unknown date format: %r", s)
    return None


def to_int(s: str | None) -> int | None:
    """숫자 문자열 → int. 빈 문자열·비숫자는 None."""
    if not s or not str(s).strip():
        return None
    try:
        return int(str(s).strip())
    except ValueError:
        return None


def to_float(s: str | None) -> float | None:
    """숫자 문자열 → float."""
    if not s or not str(s).strip():
        return None
    try:
        return float(str(s).strip())
    except ValueError:
        return None


# ── 5번 API opengCorpInfo 파서 ─────────────────────────
def parse_openg_corp_info(s: str | None) -> dict:
    """5번 API의 opengCorpInfo caret(^) 묶음 필드 파싱.

    Returns dict with keys:
        case: 'single' / 'multiple' / 'negotiation' / 'empty' / 'malformed'
        winner_name, brn, ceo_name, bid_amount, bid_rate
    """
    base = {
        "case": "empty",
        "winner_name": None,
        "brn": None,
        "ceo_name": None,
        "bid_amount": None,
        "bid_rate": None,
    }

    if not s or not str(s).strip():
        return base

    tokens = str(s).split("^")

    # Case 2: 다수 낙찰자
    if tokens[0].startswith("낙찰예정자 다수"):
        return {
            **base,
            "case": "multiple",
            "bid_amount": to_int(tokens[-2]) if len(tokens) >= 2 else None,
            "bid_rate":   to_float(tokens[-1]) if len(tokens) >= 1 else None,
        }

    # Case 1 & 3: 단일 또는 협상
    if len(tokens) >= 5:
        has_amount = bool(tokens[3].strip()) and bool(tokens[4].strip())
        return {
            "case": "single" if has_amount else "negotiation",
            "winner_name": tokens[0] or None,
            "brn":         normalize_brn(tokens[1]),
            "ceo_name":    tokens[2] or None,
            "bid_amount":  to_int(tokens[3]),
            "bid_rate":    to_float(tokens[4]),
        }

    return {**base, "case": "malformed"}
