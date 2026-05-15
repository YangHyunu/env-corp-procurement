"""
클러스터링 시각화 보고서 — HTML.

artifacts/clustering_assignments.csv + clustering_profiles.json + clustering_metrics.json
→ analysis/clustering_report.html (self-contained, SVG 내장)

사용:
  uv run python scripts/clustering_report.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "artifacts"
ANALYSIS = ROOT / "analysis"
ANALYSIS.mkdir(exist_ok=True)

# 군집별 색상 (12개 + 노이즈)
COLORS = [
    "#94a3b8",  # -1 노이즈
    "#2563eb", "#16a34a", "#d97706", "#dc2626", "#9333ea",
    "#0891b2", "#65a30d", "#c2410c", "#7c3aed", "#0284c7",
    "#ca8a04", "#be185d",
]


def color_for(cid: int) -> str:
    """Legacy fallback (cluster_id 기준) — group 매핑 없을 때만."""
    if cid < 0:
        return COLORS[0]
    return COLORS[(cid + 1) % len(COLORS)]


def color_for_cluster(cid: int, cid_to_color: dict[int, str]) -> str:
    """라벨 그룹 색상 우선 (cid_to_color), 없으면 cluster_id 색."""
    return cid_to_color.get(cid, color_for(cid))


def build_cid_to_color(profiles: list[dict]) -> dict[int, str]:
    """profiles → cluster_id → 라벨 그룹 색 매핑."""
    out: dict[int, str] = {}
    for p in profiles:
        gkey = _group_of(p)
        _, _, fg, _ = GROUP_META[gkey]
        out[p["cluster_id"]] = fg
    return out


# 라벨 그룹별 마커 모양 (산점도 + 범례 공통)
GROUP_MARKERS = {
    "real_sr":    "star",       # ★ 진짜 SR
    "auto_sr":    "diamond",    # ◆ 여성CEO 자동판별
    "veteran":    "circle",     # ●
    "new_sr":     "diamond",    # ◆ (구 호환)
    "dormant":    "triangle",   # ▲
    "high_lost":  "cross",      # ✕
    "other":      "square",     # ■
    "noise":      "ring",       # ○
}


def _marker_svg(shape: str, cx: float, cy: float, color: str, r: float = 3.0, opacity: float = 0.75) -> str:
    """SVG 마커 1개 — 라벨 그룹별 모양."""
    if shape == "circle":
        return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{color}" opacity="{opacity}"/>'
    if shape == "ring":
        return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="none" stroke="{color}" stroke-width="1.2" opacity="{opacity}"/>'
    if shape == "square":
        s = r * 1.7
        return f'<rect x="{cx-s/2:.1f}" y="{cy-s/2:.1f}" width="{s:.1f}" height="{s:.1f}" fill="{color}" opacity="{opacity}"/>'
    if shape == "diamond":
        d = r * 1.2
        pts = f"{cx:.1f},{cy-d:.1f} {cx+d:.1f},{cy:.1f} {cx:.1f},{cy+d:.1f} {cx-d:.1f},{cy:.1f}"
        return f'<polygon points="{pts}" fill="{color}" opacity="{opacity}"/>'
    if shape == "triangle":
        d = r * 1.3
        pts = f"{cx:.1f},{cy-d:.1f} {cx-d:.1f},{cy+d*0.8:.1f} {cx+d:.1f},{cy+d*0.8:.1f}"
        return f'<polygon points="{pts}" fill="{color}" opacity="{opacity}"/>'
    if shape == "cross":
        a = r * 0.9
        return (
            f'<line x1="{cx-a:.1f}" y1="{cy-a:.1f}" x2="{cx+a:.1f}" y2="{cy+a:.1f}" '
            f'stroke="{color}" stroke-width="1.6" opacity="{opacity}"/>'
            f'<line x1="{cx-a:.1f}" y1="{cy+a:.1f}" x2="{cx+a:.1f}" y2="{cy-a:.1f}" '
            f'stroke="{color}" stroke-width="1.6" opacity="{opacity}"/>'
        )
    if shape == "star":
        # 5-point star r outer / r inner ≈ 0.4
        ro = r * 1.4
        ri = ro * 0.45
        import math
        pts = []
        for i in range(10):
            angle = -math.pi / 2 + i * math.pi / 5
            rr = ro if i % 2 == 0 else ri
            pts.append(f"{cx + rr*math.cos(angle):.1f},{cy + rr*math.sin(angle):.1f}")
        return f'<polygon points="{" ".join(pts)}" fill="{color}" opacity="{opacity}"/>'
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{color}" opacity="{opacity}"/>'


def build_cid_to_marker(profiles: list[dict]) -> dict[int, str]:
    """cluster_id → 마커 모양 (그룹 기반)."""
    return {p["cluster_id"]: GROUP_MARKERS.get(_group_of(p), "circle") for p in profiles}


def render_scatter_svg(
    df: pd.DataFrame, cid_to_color: dict[int, str], cid_to_marker: dict[int, str],
    w: int = 720, h: int = 540, pad: int = 40,
) -> str:
    """UMAP 2D 산점도. 색=군집 고유, 모양=라벨 그룹."""
    x = df["umap_x"].to_numpy()
    y = df["umap_y"].to_numpy()
    cids = df["cluster_id"].to_numpy()

    x_min, x_max = x.min(), x.max()
    y_min, y_max = y.min(), y.max()
    x_range = x_max - x_min or 1
    y_range = y_max - y_min or 1

    def sx(xi: float) -> float:
        return pad + (xi - x_min) / x_range * (w - 2 * pad)

    def sy(yi: float) -> float:
        return h - pad - (yi - y_min) / y_range * (h - 2 * pad)

    points = "\n".join(
        _marker_svg(
            cid_to_marker.get(int(cid), "circle"),
            sx(xi), sy(yi),
            color_for_cluster(int(cid), cid_to_color),
            r=3.0,
        )
        for xi, yi, cid in zip(x, y, cids)
    )

    return f"""
    <svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;background:#fafbfc;border-radius:8px;">
      <rect x="0" y="0" width="{w}" height="{h}" fill="#fafbfc"/>
      <text x="{w/2:.0f}" y="20" text-anchor="middle" font-size="11" fill="#64748b" font-weight="600">UMAP 2D 임베딩 — {len(df)} BRN, {df['cluster_id'].nunique()-1 if -1 in df['cluster_id'].values else df['cluster_id'].nunique()} 군집</text>
      {points}
    </svg>
    """


def _group_of(p: dict) -> str:
    """라벨 → 그룹 매핑 (UI용)."""
    cid = p["cluster_id"]
    if cid == -1:
        return "noise"
    label = p["label"]
    # SR 신뢰도: 진짜 SR(장애인·사회적) vs 여성CEO 자동판별 분리 — 운영 정책상 중요
    if "진짜 SR" in label:
        return "real_sr"
    if "자동판별 SR" in label or "여성CEO" in label:
        return "auto_sr"
    if "베테랑" in label:
        return "veteran"
    if "활동저조" in label or "활동중단" in label:
        return "dormant"
    if "고탈락" in label:
        return "high_lost"
    if "신생 SR" in label:
        return "new_sr"
    return "other"


GROUP_META = {
    "real_sr":    ("★ 진짜 SR (장애인·사회적)", "#dcfce7", "#15803d", "real_sr_pct 50%+ — 사회적가치법 우선구매 1순위, 의무비율 가중 인정"),
    "auto_sr":    ("△ 여성CEO 자동판별 SR", "#fef9c3", "#854d0e", "sr_pct 50%+ 인데 real_sr (장애인/사회적) 50% 미만 — CSV 자동판별 비중 높음, 인증서 보유 별도 확인 필요"),
    "veteran":    ("환경공단 베테랑", "#dbeafe", "#1e40af", "평균 환경공단 낙찰 3건+ AND 탈락률 20% 미만 — 풍부한 거래 이력"),
    "new_sr":     ("신생 SR 기업", "#fce7f3", "#be185d", "SR 50%+ BUT 평균 환경공단 1건 미만 — SR 인증 신생"),
    "dormant":    ("활동저조 위험", "#fef3c7", "#92400e", "마지막 낙찰 평균 24개월+ — 사실상 inactive"),
    "high_lost":  ("고탈락 위험군", "#fee2e2", "#991b1b", "탈락률 30%+ — 1순위였으나 최종낙찰 실패 多"),
    "other":      ("기타", "#f1f5f9", "#475569", "위 조건에 해당 없음"),
    "noise":      ("분류외 노이즈", "#f1f5f9", "#64748b", "HDBSCAN 가 어느 군집에도 못 넣은 outlier — outlier"),
}


def render_legend(
    profiles: list[dict],
    cid_to_color: dict[int, str],
    cid_to_marker: dict[int, str],
) -> str:
    """그룹별로 묶어서 범례 표시. 점은 산점도와 동일한 모양 + 색."""
    grouped: dict[str, list[dict]] = {}
    for p in profiles:
        grouped.setdefault(_group_of(p), []).append(p)

    order = ["real_sr", "auto_sr", "veteran", "high_lost", "dormant", "other", "noise"]
    sections = []
    for gkey in order:
        if gkey not in grouped:
            continue
        items = grouped[gkey]
        gname, gbg, gfg, gdesc = GROUP_META[gkey]
        total_brns = sum(p["brn_count"] for p in items)
        # 그룹 헤더에 마커 모양 미니 SVG 표시
        shape = GROUP_MARKERS.get(gkey, "circle")
        head_marker = (
            f'<svg width="14" height="14" viewBox="0 0 14 14" style="flex-shrink:0;">'
            f'{_marker_svg(shape, 7, 7, gfg, r=4.5, opacity=1.0)}</svg>'
        )

        rows = ""
        for p in sorted(items, key=lambda x: -x["brn_count"]):
            cid = p["cluster_id"]
            color = color_for_cluster(cid, cid_to_color)
            marker_svg = (
                f'<svg width="14" height="14" viewBox="0 0 14 14" style="flex-shrink:0;">'
                f'{_marker_svg(shape, 7, 7, color, r=4, opacity=0.95)}</svg>'
            )
            detail = p["label"].split("(", 1)[1].rstrip(")") if "(" in p["label"] else ""
            rows += (
                f'<div style="display:flex;align-items:center;gap:8px;padding:3px 0;font-size:12px;">'
                f'{marker_svg}'
                f'<span style="color:#475569;font-variant-numeric:tabular-nums;width:26px;text-align:right;">'
                f'{("noise" if cid == -1 else f"#{cid}")}</span>'
                f'<span style="color:#94a3b8;width:46px;text-align:right;font-variant-numeric:tabular-nums;">{p["brn_count"]}</span>'
                f'<span style="color:#475569;font-size:11px;">{detail}</span>'
                f'</div>'
            )
        sections.append(f"""
        <div style="margin-bottom:14px;padding:10px 12px;background:{gbg};border-radius:6px;">
          <div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin-bottom:4px;">
            <span style="display:flex;align-items:center;gap:6px;font-weight:700;color:{gfg};font-size:12px;">
              {head_marker}{gname}
            </span>
            <span style="font-size:11px;color:{gfg};opacity:0.7;font-variant-numeric:tabular-nums;">{len(items)} 군집 · {total_brns} BRN</span>
          </div>
          <div style="font-size:10.5px;color:{gfg};opacity:0.85;margin-bottom:6px;line-height:1.4;">{gdesc}</div>
          {rows}
        </div>
        """)
    return "".join(sections)


def render_label_explanation() -> str:
    """군집 그룹(7종) 풀어서 설명 — 운영팀 공무원이 보고서로 그대로 쓸 수 있는 톤."""
    items = [
        ("★ 진짜 SR (장애인·사회적기업)", "#15803d", "#dcfce7",
         "장애인기업 또는 사회적기업 인증을 실제로 보유한 회사",
         "공식 인증서를 들고 있는 가게 — 정책상 우대 대상이 확실함",
         "사회적가치법 §7 우선구매 의무비율을 채울 때 가장 안전한 1순위 풀"),
        ("△ 여성 대표 자동등록 SR", "#854d0e", "#fef9c3",
         "조달업체 CSV에 여성기업으로 자동등록된 회사 (대표자 성별 기준)",
         "이름표만 SR — 진짜 인증서 보유 여부는 별도 확인 필요",
         "정책 가점은 받지만 실 인증 비중이 낮음. 발주 전 인증서 유효성 검증"),
        ("환경공단 주력 공급사", "#1e40af", "#dbeafe",
         "환경공단 본부·권역에 평균 3건 이상 꾸준히 공급해 온 회사",
         "단골 거래처 — 한결같이 일해주는 곳",
         "안정성 1순위. '평소 하던 데 맡기자'에 가장 잘 맞는 풀"),
        ("최근 24개월+ 무낙찰 (활동저조)", "#92400e", "#fef3c7",
         "옛날엔 거래했는데 최근 2년 이상 환경공단 낙찰을 못 받은 회사",
         "옛 단골인데 요즘 모습이 안 보임 — 폐업·휴업·사업 전환 가능성",
         "사실상 비활성 — 추천 시 활동 재개 여부 확인 필요"),
        ("1순위였다가 탈락 (고탈락 위험군)", "#991b1b", "#fee2e2",
         "1순위로 뽑혔는데 최종 낙찰을 자주 못 받는 회사",
         "면접 합격했는데 자격검증에서 자꾸 떨어지는 사람",
         "자격 미달·시담 결렬·포기 패턴 — 빨간 경고 + 운영팀 개별 검토 권고"),
        ("오래 등록된 소규모 공급사", "#d97706", "#fef3c7",
         "G2B 등록한 지 10년 넘었지만 거래량은 적은 회사",
         "노포 — 오래 살아남았지만 발주는 드물게 받음",
         "위 조건 어디에도 해당 안 될 때 fallback — '오래됨'이 유일한 특징"),
        ("분류외 (노이즈)", "#64748b", "#f1f5f9",
         "어느 군집과도 잘 묶이지 않는 outlier",
         "특이한 가게 — 활동·도메인이 너무 독특함",
         "HDBSCAN이 자동 분류 못 한 BRN. 추천 시 개별 검토 필요"),
    ]
    cards = []
    for name, fg, bg, who, analogy, usage in items:
        cards.append(f"""
        <div style="background:{bg};padding:12px 14px;border-radius:8px;border-left:3px solid {fg};">
          <div style="font-weight:700;color:{fg};font-size:13px;margin-bottom:6px;">{name}</div>
          <div style="font-size:11.5px;color:#475569;line-height:1.55;">
            <b style="color:#0f172a;">누구:</b> {who}<br>
            <b style="color:#0f172a;">비유:</b> {analogy}<br>
            <b style="color:#0f172a;">의미:</b> {usage}
          </div>
        </div>
        """)
    return f'<div style="display:grid;grid-template-columns:repeat(2, 1fr);gap:10px;">{"".join(cards)}</div>'


def render_label_rules() -> str:
    """라벨 자동 휴리스틱 규칙 표 (pipeline.clustering._label_cluster 와 동기)."""
    rules = [
        ("1", "★ 진짜 SR (장애인·사회적기업)", "real_sr_pct ≥ 50% — 장애인기업 또는 사회적기업 비중 절반 초과", "#15803d"),
        ("2", "△ 여성 대표 자동등록 SR", "sr_pct ≥ 50% AND real_sr_pct < 50% — 여성CEO 자동판별이 다수", "#854d0e"),
        ("3", "환경공단 주력 공급사", "평균 환경공단 낙찰 ≥ 3건 AND 탈락률 < 20%", "#1e40af"),
        ("4", "활동저조 (24개월+ 무낙찰)", "마지막 낙찰 평균 ≥ 24개월 전", "#92400e"),
        ("5", "1순위였다가 탈락 (고탈락 위험군)", "탈락률 (1순위 → 최종실패 비율) ≥ 30%", "#991b1b"),
        ("6", "오래 등록된 소규모 공급사", "G2B 평균 등록 연수 ≥ 10년 (위 조건 미해당)", "#d97706"),
        ("7", "기타 — 분류 애매", "위 조건 모두 해당 없음 — 미세 패턴 군집", "#475569"),
    ]
    rows = "".join(
        f'<tr>'
        f'<td style="text-align:center;color:#94a3b8;font-weight:600;">{i}</td>'
        f'<td style="font-weight:600;color:{color};">{name}</td>'
        f'<td style="color:#475569;font-size:11.5px;">{cond}</td>'
        f'</tr>'
        for i, name, cond, color in rules
    )
    return f"""
    <table style="width:100%;border-collapse:collapse;font-size:12px;">
      <thead>
        <tr>
          <th style="width:40px;text-align:center;padding:6px;border-bottom:2px solid #e2e8f0;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;">우선순위</th>
          <th style="text-align:left;padding:6px;border-bottom:2px solid #e2e8f0;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;">라벨</th>
          <th style="text-align:left;padding:6px;border-bottom:2px solid #e2e8f0;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;">조건 (앞 조건 우선)</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    <div style="font-size:11px;color:#64748b;margin-top:10px;padding:10px 12px;background:#f1f5f9;border-radius:6px;line-height:1.7;">
      <b>sr_pct 정의 (혼동 주의)</b><br>
      <code>sr_pct</code> = <b>군집 안에서 SR 인증 1개 이상 보유한 BRN의 비율</b> (BRN 단위 통계).<br>
      <span style="color:#dc2626;">≠</span> 한 BRN 의 인증 보유 비율 (3개 중 N개 — 이건 <code>avg_sr_count</code> 0~3 별도 컬럼).<br>
      예: 군집에 100 BRN 중 60 BRN 이 SR 인증 1개 이상 = sr_pct 60%.<br><br>
      <b>같은 라벨이 여러 군집에 붙는 이유</b><br>
      위 규칙은 <b>우선순위 순</b> if-elif 체인 — 첫 매칭에서 멈춤. UMAP+HDBSCAN 이 미세 패턴(권역/품목/단가)으로 분리한 군집들이 같은 라벨 조건을 만족하면 동일 라벨 부여됨.<br>
      예: <code>#1</code>과 <code>#5</code>는 둘 다 "★ 신뢰 SR" — 평균 통계는 같지만 UMAP 좌표 분리됨 (대표 prefix4·권역·단가 차이).<br>
      운영팀 검토 후 <b>대표 prefix4·권역</b> 보면서 라벨 재명명 권장.
    </div>
    """


def render_profile_cards(profiles: list[dict], cid_to_color: dict[int, str]) -> str:
    """군집별 카드 — narrative(평어체 해설) + 핵심 stats. 표 위에 배치하는 인사이트 섹션."""
    cards: list[str] = []
    # cid 정렬: 진짜 SR → 환경공단 주력 → 자동판별 SR → 활동저조 → 노이즈
    def _sort_key(p: dict) -> tuple:
        gkey = _group_of(p)
        order_map = {
            "real_sr": 0, "veteran": 1, "auto_sr": 2,
            "high_lost": 3, "dormant": 4, "other": 5, "noise": 6,
        }
        return (order_map.get(gkey, 9), -p.get("brn_count", 0))

    for p in sorted(profiles, key=_sort_key):
        cid = p["cluster_id"]
        color = color_for_cluster(cid, cid_to_color)
        gkey = _group_of(p)
        gname, gbg, gfg, _ = GROUP_META[gkey]
        narrative = p.get("narrative") or "(해설 없음)"
        item = p.get("item_label") or "—"
        region = p.get("region_label") or "—"
        amt_eok = (p.get("avg_env_award_amt") or 0) / 1e8
        real_sr_pct = (
            100.0 * (p.get("real_sr_brn_count") or 0) / p["brn_count"]
            if p.get("brn_count") else 0.0
        )
        rep_brns = ", ".join(p.get("representative_brns") or [])[:120]

        cards.append(f"""
        <div style="background:#fff;border:1px solid #e2e8f0;border-left:5px solid {color};border-radius:10px;padding:14px 16px;display:flex;flex-direction:column;gap:8px;">
          <div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;">
            <div style="font-weight:700;font-size:13px;color:#0f172a;">
              <span style="color:#94a3b8;font-weight:500;font-size:11px;">{'노이즈' if cid==-1 else f'군집 #{cid}'}</span>
              &nbsp;·&nbsp; {p["label"]}
            </div>
            <span style="background:{gbg};color:{gfg};font-size:10.5px;font-weight:700;padding:2px 8px;border-radius:10px;white-space:nowrap;">{gname}</span>
          </div>
          <div style="font-size:12.5px;color:#334155;line-height:1.7;">{narrative}</div>
          <div style="display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:4px;padding-top:8px;border-top:1px dashed #e2e8f0;font-size:11px;">
            <div><div style="color:#94a3b8;font-size:10px;">BRN 수</div><div style="font-weight:700;font-variant-numeric:tabular-nums;">{p["brn_count"]}곳</div></div>
            <div><div style="color:#94a3b8;font-size:10px;">진짜 SR</div><div style="font-weight:700;color:{'#15803d' if real_sr_pct>=50 else '#475569'};">{real_sr_pct:.0f}%</div></div>
            <div><div style="color:#94a3b8;font-size:10px;">평균 환경공단 낙찰</div><div style="font-weight:700;">{p["avg_env_award_count"]:.1f}건</div></div>
            <div><div style="color:#94a3b8;font-size:10px;">한 곳당 누적</div><div style="font-weight:700;">{amt_eok:.1f}억</div></div>
            <div><div style="color:#94a3b8;font-size:10px;">대표 품목</div><div style="font-weight:700;font-size:10.5px;">{item}</div></div>
            <div><div style="color:#94a3b8;font-size:10px;">대표 권역</div><div style="font-weight:700;">{region}</div></div>
          </div>
          <div style="font-size:10.5px;color:#64748b;margin-top:2px;font-family:ui-monospace,monospace;">대표 BRN: {rep_brns or '—'}</div>
        </div>
        """)
    return f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">{"".join(cards)}</div>'


def render_profile_table(profiles: list[dict], cid_to_color: dict[int, str]) -> str:
    rows = []
    for p in profiles:
        cid = p["cluster_id"]
        color = color_for_cluster(cid, cid_to_color)
        trusted_badge = (
            '<span style="background:#dcfce7;color:#15803d;font-size:10px;font-weight:700;'
            'padding:2px 7px;border-radius:4px;">신뢰 SR</span>'
            if p["is_sr_trusted"] else ""
        )
        rep_brns = ", ".join(p["representative_brns"][:3]) or "—"
        rep_pf4_code = p.get("representative_prefix4") or "—"
        rep_pf4 = (
            f'<b>{p.get("item_label") or rep_pf4_code}</b>'
            f'<span style="color:#94a3b8;font-size:10.5px;"> ({rep_pf4_code})</span>'
        )
        rep_region_code = p.get("representative_region") or "—"
        rep_region = (
            f'{p.get("region_label") or rep_region_code}'
            f'<span style="color:#94a3b8;font-size:10.5px;"> ({rep_region_code})</span>'
        )
        avg_age = (
            f'{p["avg_g2b_age_years"]:.1f}년'
            if p.get("avg_g2b_age_years") is not None else "—"
        )

        rows.append(f"""
        <tr>
          <td><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{color};margin-right:6px;"></span>{('noise' if cid == -1 else cid)}</td>
          <td>{p["label"]} {trusted_badge}</td>
          <td class="num">{p["brn_count"]}</td>
          <td class="num">{p["sr_pct"]:.1f}%</td>
          <td class="num">{p["avg_sr_count"]:.2f}</td>
          <td class="num">{p["avg_env_award_count"]:.1f}</td>
          <td class="num">{p["avg_env_award_amt"]/1e6:.0f}백만</td>
          <td class="num">{p["avg_bid_lost_ratio"]*100:.1f}%</td>
          <td class="num">{p["avg_dormant_months"]:.0f}개월</td>
          <td class="num">{p["avg_prefix4_diversity"]:.1f}</td>
          <td>{avg_age}</td>
          <td>{rep_pf4}</td>
          <td>{rep_region}</td>
          <td class="brn">{rep_brns}</td>
        </tr>
        """)
    return "".join(rows)


def main() -> int:
    assignments = pd.read_csv(ARTIFACTS / "clustering_assignments.csv")
    with open(ARTIFACTS / "clustering_profiles.json", encoding="utf-8") as f:
        profiles = json.load(f)
    with open(ARTIFACTS / "clustering_metrics.json", encoding="utf-8") as f:
        metrics = json.load(f)

    # 군집별 고유 색 + 라벨 그룹별 마커 모양 — 색=cluster_id, 모양=label group
    cid_to_color = {p["cluster_id"]: color_for(p["cluster_id"]) for p in profiles}
    cid_to_marker = build_cid_to_marker(profiles)
    scatter = render_scatter_svg(assignments, cid_to_color, cid_to_marker)
    legend = render_legend(profiles, cid_to_color, cid_to_marker)
    cards = render_profile_cards(profiles, cid_to_color)
    table = render_profile_table(profiles, cid_to_color)
    label_rules = render_label_rules()
    label_explanation = render_label_explanation()

    # 메트릭 요약
    sil = metrics.get("silhouette_score")
    dbi = metrics.get("davies_bouldin_score")
    sil_str = f"{sil:.3f}" if sil is not None else "—"
    dbi_str = f"{dbi:.3f}" if dbi is not None else "—"
    n_brns = metrics["n_brns"]
    n_clusters = metrics["n_clusters"]
    n_noise = metrics["n_noise"]

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>BRN 클러스터링 보고서</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, "Apple SD Gothic Neo", sans-serif; background: #f4f5f7; color: #0f172a; font-size: 13px; padding: 24px; }}
  .container {{ max-width: 1280px; margin: 0 auto; }}
  header {{ background: #fff; padding: 20px 24px; border-radius: 12px; margin-bottom: 16px; box-shadow: 0 1px 2px rgba(15,23,42,0.04); }}
  header h1 {{ font-size: 18px; font-weight: 700; letter-spacing: -0.02em; }}
  header .sub {{ font-size: 11px; color: #64748b; margin-top: 4px; }}
  .kpis {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-top: 14px; }}
  .kpi {{ background: #fafbfc; padding: 10px 12px; border-radius: 8px; }}
  .kpi .label {{ font-size: 10px; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }}
  .kpi .value {{ font-size: 18px; font-weight: 700; margin-top: 2px; font-variant-numeric: tabular-nums; }}
  .kpi.good .value {{ color: #15803d; }}
  .kpi.warn .value {{ color: #d97706; }}

  .grid {{ display: grid; grid-template-columns: 1fr 320px; gap: 16px; margin-bottom: 16px; }}
  .panel {{ background: #fff; padding: 18px 22px; border-radius: 12px; box-shadow: 0 1px 2px rgba(15,23,42,0.04); }}
  .panel h2 {{ font-size: 13px; font-weight: 700; color: #0f172a; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 12px; }}

  table {{ width: 100%; border-collapse: collapse; font-size: 11.5px; }}
  th {{ text-align: left; padding: 8px 6px; border-bottom: 2px solid #e2e8f0; color: #475569; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; font-size: 10px; }}
  td {{ padding: 8px 6px; border-bottom: 1px solid #f1f5f9; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; font-weight: 500; }}
  td.brn {{ font-family: ui-monospace, "SF Mono", monospace; font-size: 10.5px; color: #475569; }}
  tr:hover {{ background: #fafbfc; }}

  .note {{ font-size: 11px; color: #64748b; margin-top: 12px; padding: 10px 12px; background: #f1f5f9; border-radius: 6px; }}
</style>
</head>
<body>
<div class="container">

<header>
  <h1>BRN 클러스터링 보고서</h1>
  <div class="sub">환경공단 + env_domain warm BRN 다차원 군집화 — RobustScaler + UMAP + HDBSCAN</div>

  <div class="kpis">
    <div class="kpi"><div class="label">BRN 수</div><div class="value">{n_brns:,}</div></div>
    <div class="kpi"><div class="label">군집 수</div><div class="value">{n_clusters}</div></div>
    <div class="kpi"><div class="label">노이즈 BRN</div><div class="value">{n_noise} <span style="font-size:11px;color:#64748b;font-weight:500;">({100*n_noise/n_brns:.1f}%)</span></div></div>
    <div class="kpi good"><div class="label">Silhouette</div><div class="value">{sil_str}</div></div>
    <div class="kpi good"><div class="label">Davies-Bouldin</div><div class="value">{dbi_str}</div></div>
  </div>
</header>

<div class="grid">
  <div class="panel">
    <h2>UMAP 2D 임베딩</h2>
    {scatter}
    <div class="note">
      15차원 피처(공급역량/도메인/SR/리스크/가격) → RobustScaler → UMAP 2D 투영 후 HDBSCAN 군집 색상 표시.
      UMAP 좌표는 학습용 5D와 별도 모델로 안정적 시각화 보장.
    </div>
  </div>

  <div class="panel">
    <h2>군집 범례</h2>
    {legend}
  </div>
</div>

<div class="panel" style="margin-bottom:16px;">
  <h2>군집 한눈에 — 어떤 회사들인지</h2>
  <div class="note" style="margin-top:0;margin-bottom:14px;">
    각 군집을 운영팀(공무원) 시점에서 1~2줄로 풀어 설명합니다. <b>실제로 보고서·자료에 그대로 옮겨 써도 무방한 톤</b>으로 작성됐어요.
    아래 순서: 진짜 SR → 환경공단 주력 → 자동판별 SR → 고탈락 → 활동저조 → 기타 → 노이즈.
  </div>
  {cards}
</div>

<div class="panel" style="margin-bottom:16px;">
  <h2>군집 그룹 7개 — 풀어서 설명</h2>
  {label_explanation}
</div>

<div class="panel" style="margin-bottom:16px;">
  <h2>라벨 자동 분류 기준</h2>
  {label_rules}
</div>

<div class="panel">
  <h2>군집별 프로파일 (디테일 표)</h2>
  <table>
    <thead>
      <tr>
        <th>cid</th>
        <th>라벨</th>
        <th>BRN</th>
        <th title="군집 안에서 SR 인증 1개 이상 보유한 BRN의 비율">SR%</th>
        <th title="BRN당 평균 SR 인증 수 (0~3)">평균 SR수</th>
        <th>평균 낙찰</th>
        <th>평균 낙찰액</th>
        <th>탈락률</th>
        <th>활동중단</th>
        <th>품목 다양성</th>
        <th>등록 연수</th>
        <th>대표 prefix4</th>
        <th>대표 권역</th>
        <th>대표 BRN (top 3)</th>
      </tr>
    </thead>
    <tbody>{table}</tbody>
  </table>
  <div class="note">
    <b>★ 진짜 SR</b>은 장애인기업·사회적기업 비중이 절반을 넘는 군집입니다 (운영 정책상 가장 안전한 우선구매 풀).
    <b>△ 자동판별 SR</b>은 여성 대표 등록만으로 SR로 분류된 곳 비중이 큰 군집이라, 실제 인증서 보유는 별도로 확인해야 합니다.
    자동 라벨은 휴리스틱이므로 운영팀 검토 후 재명명 가능합니다.
  </div>
</div>

<div class="panel" style="margin-top:16px;">
  <h2>피처 (15)</h2>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;font-size:11.5px;">
    <div>
      <div style="font-weight:700;color:#475569;margin-bottom:6px;">A. 공급역량 (5)</div>
      <div style="color:#64748b;line-height:1.7;">
        env_award_count_total<br>
        env_award_amt_total (log)<br>
        env_avg_rate<br>
        env_dminstt_count<br>
        g2b_age_years
      </div>
    </div>
    <div>
      <div style="font-weight:700;color:#475569;margin-bottom:6px;">B. 도메인 (3) / C. SR (3)</div>
      <div style="color:#64748b;line-height:1.7;">
        prefix4_diversity<br>
        main_prdct_consistency<br>
        is_manufacturer_flag<br>
        sr_count / real_sr_flag / female_ceo_flag
      </div>
    </div>
    <div>
      <div style="font-weight:700;color:#475569;margin-bottom:6px;">D. 리스크 (2) / E. 가격 (2)</div>
      <div style="color:#64748b;line-height:1.7;">
        bid_lost_ratio<br>
        dormant_months<br>
        avg_unit_price_zscore<br>
        price_volatility
      </div>
    </div>
  </div>
</div>

</div>
</body>
</html>
"""
    out = ANALYSIS / "clustering_report.html"
    out.write_text(html, encoding="utf-8")
    print(f"saved → {out} ({len(html)/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
