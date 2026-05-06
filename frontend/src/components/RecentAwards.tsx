import type { AwardItemV2 } from '@/lib/types'

interface Props {
  awards: AwardItemV2[]
}

export function RecentAwards({ awards }: Props) {
  const list = awards.slice(0, 5)

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
        최근 낙찰 이력 {list.length}건
      </h3>

      {list.length === 0 ? (
        <div style={{ fontSize: 11, color: '#94a3b8', padding: '8px 0' }}>
          낙찰 이력 없음
        </div>
      ) : (
        <table style={{ width: '100%', fontSize: 11, borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={thStyle}>일자</th>
              <th style={thStyle}>공고명</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>낙찰액 / 낙찰률</th>
            </tr>
          </thead>
          <tbody>
            {list.map((a) => (
              <tr key={a.bid_ntce_no}>
                <td style={tdStyle}>{a.fnl_sucsf_date?.slice(0, 10) ?? '—'}</td>
                <td
                  style={{
                    ...tdStyle,
                    maxWidth: 140,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                  title={a.bid_ntce_nm ?? ''}
                >
                  {a.bid_ntce_nm ?? '—'}
                </td>
                <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                  {a.sucsfbid_amt != null
                    ? `${Math.round(a.sucsfbid_amt / 1_000_000).toLocaleString()}백만`
                    : '—'}
                  {a.sucsfbid_rate != null ? ` / ${a.sucsfbid_rate.toFixed(1)}%` : ''}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

const thStyle: React.CSSProperties = {
  textAlign: 'left',
  color: '#94a3b8',
  fontWeight: 600,
  padding: '6px 4px',
  borderBottom: '1px solid #ebedf0',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  fontSize: 10,
}

const tdStyle: React.CSSProperties = {
  padding: '7px 4px',
  borderBottom: '1px solid #f1f3f5',
  fontWeight: 500,
}
