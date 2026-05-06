import type { ComplianceInfo } from '@/lib/types'

interface Props {
  compliance: ComplianceInfo | null
  srTarget: number
  onSrTargetChange: (v: number) => void
}

const SR_OPTIONS = [15, 20, 30, 40, 50]

export function ComplianceBar({ compliance, srTarget, onSrTargetChange }: Props) {
  if (!compliance) return null

  const met = compliance.sr_pct_top_k >= srTarget
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
      <span>SR 의무비율 ≥</span>
      <select
        value={srTarget}
        onChange={(e) => onSrTargetChange(Number(e.target.value))}
        style={{
          padding: '2px 7px',
          border: '1px solid #86efac',
          background: '#fff',
          color: '#14532d',
          borderRadius: 5,
          fontSize: 11,
          fontWeight: 700,
          cursor: 'pointer',
          fontFamily: 'inherit',
          transition: 'all 0.15s',
        }}
      >
        {SR_OPTIONS.map((v) => (
          <option key={v} value={v}>
            {v}%
          </option>
        ))}
      </select>
      <span>—</span>
      <b style={{ color: met ? '#14532d' : '#991b1b', fontWeight: 700 }}>
        상위 {compliance.sr_in_top_k + (5 - srInK > 0 ? (5 - srInK) : 0)}개 후보 중 정책 인증 기업 {srInK}개 ({pct.toFixed(0)}%)
      </b>
      <span style={{ color: met ? '#15803d' : '#b91c1c' }}>
        {met ? '충족' : '미충족'}
      </span>
      <span style={{ marginLeft: 'auto', fontSize: 10, color: '#9ca3af' }}>
        기관 설정 기준 적용
      </span>
    </div>
  )
}
