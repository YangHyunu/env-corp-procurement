import type { RecommendationV2Item } from '@/lib/types'
import { SrBadge, TierBadge } from '@/lib/badges'

// 가격 신뢰도 등급 — n_samples / is_extrapolated 기반
function PriceConfidenceBadge({ n, isExtrapolated }: { n: number; isExtrapolated: boolean }) {
  let stars: string
  let label: string | null = null

  if (isExtrapolated) {
    stars = '★'          // ★
    label = '시장평균 추정'
  } else if (n >= 3) {
    stars = '★★★' // ★★★
  } else {
    stars = '★★'    // ★★
    label = `참고용 (n=${n})`
  }

  return (
    <div style={{ marginTop: 2, fontSize: 9.5, lineHeight: 1.2 }}>
      <span style={{ color: '#fbbf24', letterSpacing: '-0.03em' }}>{stars}</span>
      {label && (
        <span style={{ color: '#9ca3af', marginLeft: 3, fontWeight: 400 }}>{label}</span>
      )}
    </div>
  )
}

interface Props {
  item: RecommendationV2Item
  selected: boolean
  compareMode: boolean
  inCompare: boolean
  onSelect: () => void
  onToggleCompare: () => void
}

export function RecommendationCard({
  item,
  selected,
  compareMode,
  inCompare,
  onSelect,
  onToggleCompare,
}: Props) {
  const stats = item.summary_stats
  const price = item.expected_price
  const tier = item.tier

  const cardBorder = selected
    ? '0 0 0 2px #4f46e5, 0 4px 12px rgba(15,23,42,0.06)'
    : inCompare
      ? '0 0 0 2px #f59e0b, 0 4px 12px rgba(15,23,42,0.06)'
      : '0 1px 2px rgba(15,23,42,0.04), 0 1px 3px rgba(15,23,42,0.05)'

  const cardBg = selected
    ? 'linear-gradient(180deg, #fafbff 0%, #ffffff 60%)'
    : inCompare
      ? 'linear-gradient(180deg, #fffbeb 0%, #ffffff 60%)'
      : '#fff'

  return (
    <div
      onClick={onSelect}
      style={{
        background: cardBg,
        borderRadius: 10,
        padding: '12px 14px',
        cursor: 'pointer',
        display: 'grid',
        gridTemplateColumns: '32px 1fr auto',
        gap: 12,
        alignItems: 'center',
        transition: 'all 0.18s',
        boxShadow: cardBorder,
        userSelect: 'none',
      }}
      onMouseEnter={(e) => {
        if (!selected && !inCompare) {
          e.currentTarget.style.transform = 'translateY(-1px)'
          e.currentTarget.style.boxShadow =
            '0 4px 12px rgba(15,23,42,0.06), 0 2px 4px rgba(15,23,42,0.04)'
        }
      }}
      onMouseLeave={(e) => {
        if (!selected && !inCompare) {
          e.currentTarget.style.transform = 'none'
          e.currentTarget.style.boxShadow =
            '0 1px 2px rgba(15,23,42,0.04), 0 1px 3px rgba(15,23,42,0.05)'
        }
      }}
    >
      {/* 랭크 / 비교 체크 */}
      <div style={{ textAlign: 'center' }}>
        {compareMode ? (
          <input
            type="checkbox"
            checked={inCompare}
            onChange={(e) => {
              e.stopPropagation()
              onToggleCompare()
            }}
            onClick={(e) => e.stopPropagation()}
            style={{ accentColor: '#f59e0b', width: 16, height: 16, cursor: 'pointer' }}
          />
        ) : (
          <span
            style={{
              fontSize: 18,
              fontWeight: 800,
              color: selected ? '#4f46e5' : '#94a3b8',
              letterSpacing: '-0.04em',
            }}
          >
            #{item.rank}
          </span>
        )}
      </div>

      {/* 업체 정보 */}
      <div>
        <div
          style={{
            fontWeight: 700,
            fontSize: 13,
            letterSpacing: '-0.01em',
          }}
        >
          {item.corp_name ?? item.brn}
          <span
            style={{
              fontSize: 10,
              fontWeight: 400,
              color: '#6b7280',
              fontFamily: 'ui-monospace, "SF Mono", Consolas, monospace',
              marginLeft: 6,
            }}
          >
            {item.brn}
          </span>
        </div>

        {/* 뱃지 */}
        <div style={{ display: 'inline-flex', gap: 4, flexWrap: 'wrap', marginTop: 5 }}>
          <TierBadge tier={tier} />
          {item.badges.map((b) => (
            <SrBadge key={b} label={b} />
          ))}
          {item.cluster_label != null && (
            <span
              style={{
                fontSize: 9,
                padding: '2px 7px',
                borderRadius: 5,
                fontWeight: 700,
                letterSpacing: '0.01em',
                background: '#e0f2fe',
                color: '#0369a1',
              }}
            >
              {item.cluster_label}
            </span>
          )}
        </div>

        {/* 메타 */}
        <div
          style={{
            fontSize: 10.5,
            color: '#475569',
            marginTop: 4,
            fontWeight: 500,
          }}
        >
          환경공단 낙찰 {stats.award_count}건
          {stats.avg_bid_rate != null ? ` · 평균 ${stats.avg_bid_rate.toFixed(1)}%` : ''}
          {stats.lost_count > 0 ? ` · 탈락 ${stats.lost_count}` : ''}
          {stats.last_award_at ? ` · 최근 ${stats.last_award_at.slice(0, 7)}` : ''}
        </div>

        {/* KNN 유사 사례 */}
        {item.knn_similar_corp_name != null && item.knn_similarity != null && (
          <div
            style={{
              fontSize: 10,
              color: '#6b7280',
              marginTop: 3,
              fontStyle: 'italic',
            }}
          >
            유사 사례: {item.knn_similar_corp_name} 와 {Math.round(item.knn_similarity * 100)}% 유사
          </div>
        )}
      </div>

      {/* 우측 가격/점수 */}
      <div style={{ textAlign: 'right' }}>
        {/* 가격 숫자 + 신뢰도 등급 */}
        <div
          style={{
            fontSize: 14,
            fontWeight: 800,
            fontVariantNumeric: 'tabular-nums',
            letterSpacing: '-0.02em',
          }}
        >
          {price.point_million.toLocaleString()}
          <span style={{ fontSize: 9, color: '#94a3b8', fontWeight: 500, marginLeft: 1 }}>
            백만
          </span>
        </div>
        {/* 신뢰도 별 등급 */}
        <PriceConfidenceBadge n={price.n_samples} isExtrapolated={price.is_extrapolated ?? false} />
        {/* 시장가 분위수 — 3필드 모두 non-null 일 때만 표시 */}
        {price.market_q25_million != null &&
          price.market_q50_million != null &&
          price.market_q75_million != null && (
            <div
              style={{
                fontSize: 9.5,
                color: '#94a3b8',
                marginTop: 2,
                fontStyle: 'italic',
                fontVariantNumeric: 'tabular-nums',
                whiteSpace: 'nowrap',
              }}
            >
              시장가: {price.market_q25_million}~{price.market_q75_million}M (중앙 {price.market_q50_million}M)
            </div>
          )}
        <div
          style={{
            fontSize: 10,
            color: '#94a3b8',
            marginTop: 3,
            fontWeight: 500,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          종합점수 {item.rule_score.toFixed(2)}
        </div>
      </div>
    </div>
  )
}

