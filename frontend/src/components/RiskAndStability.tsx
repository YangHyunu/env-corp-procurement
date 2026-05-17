import type { RiskInfo, SupplyStability } from '@/lib/types'
import { riskLabel } from '@/lib/utils'
import { RISK_GRADE_COLORS } from '@/lib/badges'

interface Props {
  risk: RiskInfo
  stability: SupplyStability
}

export function RiskAndStability({ risk, stability }: Props) {
  const grade = riskLabel(risk.grade)
  const pillStyle = RISK_GRADE_COLORS[grade] ?? RISK_GRADE_COLORS.미확인

  const totalAmt = stability.award_total_amt
  const totalAmtLabel =
    totalAmt >= 1_000_000_000
      ? `${(totalAmt / 1_000_000_000).toFixed(1)}억`
      : totalAmt >= 1_000_000
        ? `${(totalAmt / 1_000_000).toFixed(0)}만원`
        : `${totalAmt.toLocaleString()}원`

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
        위험요인 및 공급 안정성
      </h3>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* 위험 */}
        <div>
          <div style={{ marginBottom: 8 }}>
            <span
              style={{
                display: 'inline-block',
                padding: '4px 11px',
                borderRadius: 999,
                fontSize: 11,
                fontWeight: 700,
                ...pillStyle,
              }}
            >
              위험등급: {grade}
            </span>
          </div>
          <StatRow label="1순위 누적" value={`${risk.top1_count}회`} />
          <StatRow label="최종낙찰 실패" value={`${risk.lost_count}회`} />
          <StatRow label="최근 1년 탈락" value={`${risk.recent_lost}회`} />
          <StatRow
            label="최근 활동 확인"
            value={
              risk.dormant_months != null
                ? `${risk.dormant_months}개월 전`
                : stability.last_award_at
                  ? `${monthsAgo(stability.last_award_at)}개월 전`
                  : '—'
            }
            valueColor={!risk.is_dormant ? '#15803d' : '#dc2626'}
          />
        </div>

        {/* 공급 안정성 */}
        <div>
          <StatRow
            label="나라장터 등록 기간"
            value={
              stability.g2b_age_years != null
                ? `${stability.g2b_age_years.toFixed(1)}년`
                : '—'
            }
          />
          <StatRow label="총 낙찰액" value={totalAmtLabel} />
          <StatRow
            label="자체 제조 여부"
            value={stability.is_manufacturer ? '예' : '아니오'}
          />
          <StatRow
            label="최근 낙찰"
            value={stability.last_award_at?.slice(0, 7) ?? '—'}
          />
        </div>
      </div>
    </div>
  )
}

function StatRow({
  label,
  value,
  valueColor,
}: {
  label: string
  value: string
  valueColor?: string
}) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        padding: '4px 0',
        fontSize: 11.5,
      }}
    >
      <span style={{ color: '#475569', fontWeight: 500 }}>{label}</span>
      <span
        style={{
          fontWeight: 600,
          fontVariantNumeric: 'tabular-nums',
          color: valueColor ?? '#0f172a',
        }}
      >
        {value}
      </span>
    </div>
  )
}

function monthsAgo(dateStr: string): number {
  const d = new Date(dateStr)
  const now = new Date()
  return (
    (now.getFullYear() - d.getFullYear()) * 12 + (now.getMonth() - d.getMonth())
  )
}
