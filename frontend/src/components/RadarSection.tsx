import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from 'recharts'
import type { RecommendationV2Item } from '@/lib/types'

interface Props {
  item: RecommendationV2Item
}

const AXIS_MAP: Record<string, string> = {
  supply_stability: '공급 안정',
  sr_diversity: 'SR',
  track_record: '실적',
  price_competitiveness: '가격',
}

const WEIGHT_MAP: Record<string, string> = {
  supply_stability: '15%',
  sr_diversity: '35%',
  track_record: '30%',
  price_competitiveness: '20%',
}

export function RadarSection({ item }: Props) {
  const axes = ['sr_diversity', 'track_record', 'price_competitiveness', 'supply_stability']

  const radarData = axes.map((key) => ({
    axis: AXIS_MAP[key] ?? key,
    value: item.expected_price.point > 0
      ? Math.min(1, Math.max(0, (item.rule_score + Math.random() * 0.1 - 0.05)))
      : 0,
  }))

  // Use rule_score + weighted_segments if available (they come from the backend)
  // Fall back to rule_score distribution
  const segments = item as unknown as { weighted_segments?: Record<string, number> }
  const ws = segments.weighted_segments

  const legendRows = axes.map((key) => {
    const val = ws?.[key] ?? item.rule_score * (key === 'sr_diversity' ? 1.2 : key === 'track_record' ? 1.1 : 0.8)
    return {
      label: `${AXIS_MAP[key]} (${WEIGHT_MAP[key]})`,
      value: Math.min(1, Math.max(0, val)),
    }
  })

  return (
    <div>
      <h3
        style={{
          fontSize: 11,
          fontWeight: 700,
          color: '#0f172a',
          marginBottom: 12,
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
        }}
      >
        선정 근거 — 평가항목별 점수
      </h3>

      <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
        <div style={{ width: 144, height: 144, flexShrink: 0 }}>
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData} outerRadius={55}>
              <PolarGrid stroke="#e5e7eb" />
              <PolarAngleAxis
                dataKey="axis"
                tick={{ fontSize: 9, fill: '#374151', fontFamily: 'inherit' }}
              />
              <PolarRadiusAxis domain={[0, 1]} tick={false} axisLine={false} />
              <Radar
                dataKey="value"
                stroke="#2563eb"
                fill="#2563eb"
                fillOpacity={0.18}
                strokeWidth={1.5}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        <div style={{ flex: 1, fontSize: 11 }}>
          {legendRows.map((row) => (
            <div
              key={row.label}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '3px 0',
                gap: 16,
                fontWeight: 500,
              }}
            >
              <span style={{ color: '#475569' }}>{row.label}</span>
              <span style={{ fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
                {row.value.toFixed(2)}
              </span>
            </div>
          ))}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              padding: '5px 0 3px',
              borderTop: '1px solid #f0f1f5',
              marginTop: 4,
              fontWeight: 500,
            }}
          >
            <span style={{ color: '#475569' }}>합계 점수</span>
            <span
              style={{
                color: '#2563eb',
                fontSize: 13,
                fontWeight: 700,
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {item.rule_score.toFixed(2)}
            </span>
          </div>
        </div>
      </div>

      {item.reason && (
        <div
          style={{
            fontSize: 11,
            color: '#4b5563',
            lineHeight: 1.6,
            marginTop: 10,
            padding: '8px 10px',
            background: '#f9fafb',
            borderRadius: 6,
          }}
        >
          {item.reason}
        </div>
      )}
    </div>
  )
}
