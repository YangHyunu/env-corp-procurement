"""
g2b_opening.py — 5번 API (getOpengResultListInfoThng) 수집 모듈.

raw 적재만 담당. opengCorpInfo 파싱은 stg 단계에서
g2b_common.parse_openg_corp_info 사용.

CLAUDE.md 함정:
- bidNtceNo size 정의(11) vs 실제(13) — VARCHAR(20)으로 안전망
- progrsDivCdNm = 유찰/개찰완료/재입찰 — 유찰 시 opengCorpInfo 빈 값 가능
- raw PK = (fetched_at, bid_ntce_no, bid_ntce_ord, bid_clsfc_no, rbid_no)
- 한 공고에 재입찰 차수가 여러 개 → page_size=100 권장
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Iterator

import requests

from .g2b_common import make_session, paginate

logger = logging.getLogger(__name__)

OPERATION = "as/ScsbidInfoService/getOpengResultListInfoThng"


def iter_items_for_bid(
    bid_ntce_no: str,
    *,
    page_size: int = 100,
    session: requests.Session | None = None,
) -> Iterator[tuple[ET.Element, dict]]:
    """단일 bidNtceNo로 inqryDiv=4 룩업.

    한 공고당 보통 1~수 건 (재입찰 시 여러 차수). page_size=100이면 충분.
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
    """raw_g2b_opening INSERT용 dict.

    PK 4필드는 모두 응답에 존재.
    유찰 시 opengCorpInfo는 빈 값일 수 있으나 raw 단계에선 그대로 보존.
    """
    return {
        "bid_ntce_no": (item.findtext("bidNtceNo") or "").strip(),
        "bid_ntce_ord": (item.findtext("bidNtceOrd") or "").strip(),
        "bid_clsfc_no": (item.findtext("bidClsfcNo") or "").strip(),
        "rbid_no": (item.findtext("rbidNo") or "").strip(),
        "request_params": request_params,
        "item_xml": ET.tostring(item, encoding="unicode"),
    }
