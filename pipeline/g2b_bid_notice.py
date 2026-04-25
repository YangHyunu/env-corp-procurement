"""
g2b_bid_notice.py — 14번 API (getBidPblancListInfoThngPPSSrch) 수집 모듈.

raw 적재만 담당. stg 정규화는 별도 단계에서 수행.

CLAUDE.md 함정 체크리스트 준수:
- bidNtceNo는 size 정의(11/40) 무시하고 13자리 그대로 보존
- bidNtceOrd는 zero-pad 3자리 (응답이 "000")
- request_params와 item_xml을 같이 보존해 향후 재파싱 가능
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Iterator

import requests

from .g2b_common import make_session, paginate

logger = logging.getLogger(__name__)

OPERATION = "ad/BidPublicInfoService/getBidPblancListInfoThngPPSSrch"


def iter_items(
    *,
    inqry_bgn_dt: str,
    inqry_end_dt: str,
    dminstt_cd: str,
    inqry_div: str = "1",          # 1 = 공고게시일시 기준
    page_size: int = 100,
    session: requests.Session | None = None,
) -> Iterator[tuple[ET.Element, dict]]:
    """단일 (윈도우 × dminstt_cd) 페이징 호출.

    각 item에 대해 (xml Element, request_params dict) 쌍을 yield.
    request_params는 raw 테이블에 그대로 저장하기 위한 메타.
    """
    params = {
        "inqryDiv": inqry_div,
        "inqryBgnDt": inqry_bgn_dt,
        "inqryEndDt": inqry_end_dt,
        "dminsttCd": dminstt_cd,
    }
    request_params = {**params, "page_size": page_size}
    session = session or make_session()
    for it in paginate(OPERATION, params, page_size=page_size, session=session):
        yield it, request_params


def extract_raw_row(item: ET.Element, request_params: dict) -> dict:
    """raw_g2b_bid_notice INSERT용 dict 생성.

    bid_ntce_no/ord는 PK 일부라 NULL이면 안 됨. 14번 응답에서 결측 0%
    실측 (probe_env_corp_bids.py 결과) → 빈 문자열로 폴백 후 호출자가 검증.
    """
    return {
        "bid_ntce_no": (item.findtext("bidNtceNo") or "").strip(),
        "bid_ntce_ord": (item.findtext("bidNtceOrd") or "").strip(),
        "request_params": request_params,
        "item_xml": ET.tostring(item, encoding="unicode"),
    }
