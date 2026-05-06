import type { RecommendationV2Item, KpiV2 } from '@/lib/types'
import { SrBadge, TierBadge } from '@/lib/badges'
import { RadarSection } from './RadarSection'
import { PriceBar } from './PriceBar'
import { RiskAndStability } from './RiskAndStability'
import { RecentAwards } from './RecentAwards'
import { ActionBar } from './ActionBar'

interface Props {
  item: RecommendationV2Item | null
  kpi: KpiV2 | null
  onAddToCompare: () => void
  inCompare: boolean
}

export function DetailPanel({ item, kpi, onAddToCompare, inCompare }: Props) {
  if (!item) {
    return (
      <aside
        style={{
          background: '#fff',
          borderRadius: 14,
          boxShadow: '0 1px 2px rgba(15,23,42,0.04), 0 1px 3px rgba(15,23,42,0.05)',
          position: 'sticky',
          top: 84,
          maxHeight: 'calc(100vh - 100px)',
          overflowY: 'auto',
        }}
      >
        <div
          style={{
            padding: '80px 40px',
            textAlign: 'center',
            color: '#94a3b8',
            fontSize: 13,
            lineHeight: 1.6,
          }}
        >
          <div style={{ fontSize: 28, marginBottom: 12 }}>←</div>
          <div>카드를 클릭하면</div>
          <div>상세 정보가 표시됩니다</div>
        </div>
      </aside>
    )
  }

  const stability = item.supply_stability
  const ageYears = stability.g2b_age_years

  return (
    <aside
      style={{
        background: '#fff',
        borderRadius: 14,
        boxShadow: '0 1px 2px rgba(15,23,42,0.04), 0 1px 3px rgba(15,23,42,0.05)',
        position: 'sticky',
        top: 84,
        maxHeight: 'calc(100vh - 100px)',
        overflowY: 'auto',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* 헤더 */}
      <div
        style={{
          padding: '18px 22px',
          background: 'linear-gradient(180deg, #fafbff 0%, #ffffff 100%)',
          borderBottom: '1px solid #f1f3f5',
          flexShrink: 0,
        }}
      >
        <div
          style={{
            fontSize: 19,
            fontWeight: 800,
            marginBottom: 5,
            letterSpacing: '-0.02em',
          }}
        >
          {item.corp_name ?? item.brn}
        </div>
        <div
          style={{
            fontSize: 11,
            color: '#94a3b8',
            fontFamily: 'ui-monospace, "SF Mono", Consolas, monospace',
          }}
        >
          {item.brn}
        </div>
        <div
          style={{
            display: 'flex',
            gap: 5,
            flexWrap: 'wrap',
            marginTop: 10,
            alignItems: 'center',
          }}
        >
          <TierBadge tier={item.tier} />
          {item.badges.map((b) => (
            <SrBadge key={b} label={b} />
          ))}
          {ageYears != null && (
            <span
              style={{
                fontSize: 11,
                color: '#6b7280',
                marginLeft: 'auto',
              }}
            >
              {Math.floor(ageYears)}년 등록 ({ageYears.toFixed(1)}년)
            </span>
          )}
        </div>
      </div>

      {/* 스크롤 가능 섹션들 */}
      <div style={{ overflowY: 'auto', flex: 1 }}>
        {/* 평가항목별 점수 */}
        <DetailSection>
          <RadarSection item={item} />
        </DetailSection>

        {/* 예상 가격 */}
        <DetailSection>
          <PriceBar price={item.expected_price} kpi={kpi} />
        </DetailSection>

        {/* 위험요인 + 공급안정성 */}
        <DetailSection>
          <RiskAndStability risk={item.risk} stability={item.supply_stability} />
        </DetailSection>

        {/* 최근 낙찰 이력 */}
        <DetailSection last>
          <RecentAwards awards={item.recent_awards} />
        </DetailSection>
      </div>

      {/* 액션 바 */}
      <div style={{ flexShrink: 0, borderTop: '1px solid #f1f3f5' }}>
        <ActionBar onAddToCompare={onAddToCompare} inCompare={inCompare} />
      </div>
    </aside>
  )
}

function DetailSection({
  children,
  last,
}: {
  children: React.ReactNode
  last?: boolean
}) {
  return (
    <div
      style={{
        padding: '16px 22px',
        borderBottom: last ? 'none' : '1px solid #f1f3f5',
      }}
    >
      {children}
    </div>
  )
}

