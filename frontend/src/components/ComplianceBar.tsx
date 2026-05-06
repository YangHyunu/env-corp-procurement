import type { ComplianceInfo } from '@/lib/types'

interface Props {
  compliance: ComplianceInfo | null
  topK: number
}

export function ComplianceBar({ compliance, topK }: Props) {
  if (!compliance) return null

  const met = compliance.obligation_met
  const threshold = compliance.obligation_threshold_pct
  const srInK = compliance.sr_in_top_k
  const pct = compliance.sr_pct_top_k

  return (
    <div
      style={{
        padding: '11px 14px',
        background: met ? '#f0fdf4' : '#fef2f2',
        borderRadius: 10,
        fontSize: 11,
        display: 'flex',
        gap: 10,
        alignItems: 'center',
        marginBottom: 14,
        cursor: 'help',
        fontWeight: 500,
        boxShadow: met
          ? '0 1px 2px rgba(15,23,42,0.04), inset 0 0 0 1px rgba(34,197,94,0.2)'
          : '0 1px 2px rgba(15,23,42,0.04), inset 0 0 0 1px #fecaca',
      }}
      title="조달사업법 시행령 제24조 — 사회적가치 우선구매 의무비율"
    >
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          flexShrink: 0,
          background: met ? '#16a34a' : '#b91c1c',
          boxShadow: met
            ? '0 0 0 3px rgba(34,197,94,0.18)'
            : '0 0 0 3px rgba(239,68,68,0.18)',
        }}
      />
      <span>SR 의무비율 ≥ <b>{threshold.toFixed(0)}%</b> (법정)</span>
      <span>—</span>
      <b style={{ color: met ? '#14532d' : '#991b1b', fontWeight: 700 }}>
        상위 {topK}개 후보 중 정책 인증 기업 {srInK}개 ({pct.toFixed(0)}%)
      </b>
      <span style={{ color: met ? '#15803d' : '#b91c1c' }}>
        {met ? '충족' : '미충족'}
      </span>
      <span style={{ marginLeft: 'auto', fontSize: 10, color: '#9ca3af' }}>
        서버 판정 기준
      </span>
    </div>
  )
}
