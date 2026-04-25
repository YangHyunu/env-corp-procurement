"""
g2b_award.py — 1번 API (getScsbidListSttusThng) 수집 모듈.

raw 적재만 담당. BRN 정규화·정정공고 dedupe 등은 stg 단계에서.

CLAUDE.md 함정 체크:
- bidwinnrBizno 이미 10자리 (정규화 거의 불필요, stg에서 normalize_brn으로 안전망)
- 핸드폰 마스킹 '*' → null 변환은 stg
- raw PK = (fetched_at, bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no)
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Iterator

import requests

from .g2b_common import make_session, paginate

logger = logging.getLogger(__name__)

OPERATION = "as/ScsbidInfoService/getScsbidListSttusThng"


def iter_items_for_bid(
    bid_ntce_no: str,
    *,
    page_size: int = 999,
    session: requests.Session | None = None,
) -> Iterator[tuple[ET.Element, dict]]:
    """단일 bidNtceNo로 inqryDiv=4 룩업.

    한 공고당 보통 1~수 건이라 page_size=999면 한 페이지에 끝남.
    """
    params = {
        "inqryDiv": "4",
        "bidNtceNo": bid_ntce_no,
    }
    request_params = {**params, "page_size": page_size}
    session = session or make_session()
    for it in paginate(OPERATION, params, page_size=page_size, session=session):
        yield it, request_params


def extract_raw_row(item: ET.Element, request_params: dict) -> dict:
    """raw_g2b_award INSERT용 dict.

    PK 4필드는 반드시 추출. 응답 결측 0% 실측(probe_award.py).
    """
    return {
        "bid_ntce_no": (item.findtext("bidNtceNo") or "").strip(),
        "bid_ntce_ord": (item.findtext("bidNtceOrd") or "").strip(),
        "bid_clsfc_no": (item.findtext("bidClsfcNo") or "").strip(),
        "rbid_no": (item.findtext("rbidNo") or "").strip(),
        "request_params": request_params,
        "item_xml": ET.tostring(item, encoding="unicode"),
    }
