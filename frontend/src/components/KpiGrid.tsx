import type { KpiV2 } from '@/lib/types'

interface Props {
  kpi: KpiV2 | null
  budgetMillion: number
}

export function KpiGrid({ kpi, budgetMillion }: Props) {
  if (!kpi) return null

  const avgPrice = kpi.avg_expected_price_million
  // 평균 예상 낙찰률 — avg_expected_price_million / budgetMillion * 100
  const avgRate =
    avgPrice != null && budgetMillion > 0
      ? (avgPrice / budgetMillion) * 100
      : null

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 10,
        marginBottom: 14,
      }}
    >
      <KpiCard
        label="후보 업체"
        value={`${kpi.pool_size}`}
        delta={`등록 ${kpi.market_depth.registered} · 활동 ${kpi.market_depth.env_active}`}
      />
      <KpiCard
        label="정책 인증 보유 후보"
        value={
          <>
            {kpi.sr_count}{' '}
            <span style={{ fontSize: 10, fontWeight: 500, color: '#6b7280' }}>
              {kpi.sr_pct.toFixed(0)}%
            </span>
          </>
        }
        delta={`SR 보유 ${kpi.sr_count}개`}
      />
      <KpiCard
        label="평균 예상 낙찰률"
        value={
          avgRate != null ? (
            <>
              {avgRate.toFixed(1)}
              <span style={{ fontSize: 10, fontWeight: 500, color: '#6b7280' }}>%</span>
            </>
          ) : (
            '—'
          )
        }
        delta={
          avgPrice != null
            ? `예산 ${budgetMillion.toLocaleString()} × ${avgRate?.toFixed(1) ?? '—'}% ≈ ${avgPrice.toLocaleString()}만원`
            : '—'
        }
      />
      <KpiCard
        label="계약방식 검토안"
        value={<span style={{ fontSize: 14 }}>{kpi.contract_recommend}</span>}
        delta={`후보 ${kpi.pool_size} · 공급위험 ${kpi.supply_risk}`}
      />
    </div>
  )
}

function KpiCard({
  label,
  value,
  delta,
  tooltip,
}: {
  label: string
  value: React.ReactNode
  delta: string
  tooltip?: string
}) {
  return (
    <div
      title={tooltip}
      style={{
        background: '#fff',
        borderRadius: 10,
        padding: '12px 14px',
        boxShadow: '0 1px 2px rgba(15,23,42,0.04), 0 1px 3px rgba(15,23,42,0.05)',
        transition: 'box-shadow 0.2s',
        cursor: tooltip ? 'help' : 'default',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow =
          '0 4px 12px rgba(15,23,42,0.06), 0 2px 4px rgba(15,23,42,0.04)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow =
          '0 1px 2px rgba(15,23,42,0.04), 0 1px 3px rgba(15,23,42,0.05)'
      }}
    >
      <div
        style={{
          fontSize: 10,
          color: '#94a3b8',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 19,
          fontWeight: 800,
          marginTop: 4,
          fontVariantNumeric: 'tabular-nums',
          letterSpacing: '-0.02em',
        }}
      >
        {value}
      </div>
      <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 2, fontWeight: 500 }}>
        {delta}
      </div>
    </div>
  )
}
