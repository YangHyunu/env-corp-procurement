"""
g2b_prepar.py — 9번 API (getOpengResultListInfoThngPreparPcDetail) 수집 모듈.

한 공고당 15개 예가 row. raw 적재만 담당.

CLAUDE.md 함정:
- inqryDiv 의미가 다름 — 9번은 2=입찰공고번호 (1·5번은 4)
- 한 응답에 15 row → page_size=30이면 한 페이지에 끝남
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Iterator

import requests

from .g2b_common import make_session, paginate, to_int

logger = logging.getLogger(__name__)

OPERATION = "as/ScsbidInfoService/getOpengResultListInfoThngPreparPcDetail"


def iter_items_for_bid(
    bid_ntce_no: str,
    *,
    page_size: int = 30,
    session: requests.Session | None = None,
) -> Iterator[tuple[ET.Element, dict]]:
    """단일 bidNtceNo로 inqryDiv=2 룩업."""
    params = {
        "inqryDiv": "2",          # 9번에서 2=입찰공고번호
        "bidNtceNo": bid_ntce_no,
    }
    request_params = {**params, "page_size": page_size}
    session = session or make_session()
    for it in paginate(OPERATION, params, page_size=page_size, session=session):
        yield it, request_params


def extract_raw_row(item: ET.Element, request_params: dict) -> dict:
    """raw_g2b_prepar INSERT용 dict.

    PK 5필드 (4개 + 예가 일련번호).
    """
    return {
        "bid_ntce_no":  (item.findtext("bidNtceNo") or "").strip(),
        "bid_ntce_ord": (item.findtext("bidNtceOrd") or "").strip(),
        "bid_clsfc_no": (item.findtext("bidClsfcNo") or "").strip(),
        "rbid_no":      (item.findtext("rbidNo") or "").strip(),
        "prce_sno":     to_int(item.findtext("compnoRsrvtnPrceSno")),
        "request_params": request_params,
        "item_xml":     ET.tostring(item, encoding="unicode"),
    }
