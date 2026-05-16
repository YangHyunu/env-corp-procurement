import type { KpiV2 } from '@/lib/types'

interface Props {
  kpi: KpiV2 | null
  budgetMillion: number
}

export function KpiGrid({ kpi, budgetMillion }: Props) {
  if (!kpi) return null

  const avgPrice = kpi.avg_expected_price_million
  const budgetDiff =
    avgPrice != null && budgetMillion > 0
      ? ((avgPrice - budgetMillion) / budgetMillion) * 100
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
        label="평균 예상가"
        value={
          avgPrice != null ? (
            <>
              {avgPrice.toLocaleString()}
              <span style={{ fontSize: 10, fontWeight: 500, color: '#6b7280' }}>백만</span>
            </>
          ) : (
            '—'
          )
        }
        delta={
          budgetDiff != null
            ? `예산 대비 ${budgetDiff >= 0 ? '+' : ''}${budgetDiff.toFixed(0)}%`
            : '—'
        }
      />
      <KpiCard
        label="계약방식 검토안"
        value={<span style={{ fontSize: 14 }}>{kpi.contract_recommend}</span>}
        delta={`후보 ${kpi.pool_size} · 공급위험 ${kpi.supply_risk}`}
      />
      <div style={{ gridColumn: '1 / -1' }}>
        <KpiCard
          label="후보 분산도"
          tooltip="후보 풀의 4축 점수 분산도 (0~1). 낮으면 후보들이 비슷해서 차별화가 어렵습니다. 점수·랭킹에는 영향 없음 (보조 KPI)."
          value={
            kpi.pool_entropy != null ? (
              kpi.pool_entropy.toFixed(2)
            ) : (
              '—'
            )
          }
          delta={
            kpi.pool_entropy != null
              ? kpi.pool_entropy < 0.4
                ? '분산 낮음 — 차별화 어려움'
                : kpi.pool_entropy < 0.7
                ? '분산 보통'
                : '분산 높음 — 후보 차이 뚜렷'
              : '데이터 부족'
          }
        />
      </div>
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
