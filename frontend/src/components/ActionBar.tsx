import { FileText, Printer, GitCompare, ExternalLink } from 'lucide-react'

interface Props {
  onAddToCompare: () => void
  inCompare: boolean
}

export function ActionBar({ onAddToCompare, inCompare }: Props) {
  return (
    <div
      style={{
        padding: '14px 22px',
        background: '#fafbfc',
        display: 'flex',
        gap: 8,
        flexWrap: 'wrap',
      }}
    >
      <ActionBtn icon={<FileText size={12} />} label="검토 메모" primary />
      <ActionBtn icon={<Printer size={12} />} label="PDF 출력" onClick={() => window.print()} />
      <ActionBtn
        icon={<GitCompare size={12} />}
        label={inCompare ? '비교에서 제거' : '비교에 추가'}
        onClick={onAddToCompare}
      />
      <ActionBtn
        icon={<ExternalLink size={12} />}
        label="전체 이력"
        style={{ marginLeft: 'auto' }}
      />
    </div>
  )
}

function ActionBtn({
  icon,
  label,
  primary,
  onClick,
  style,
}: {
  icon: React.ReactNode
  label: string
  primary?: boolean
  onClick?: () => void
  style?: React.CSSProperties
}) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '8px 14px',
        border: primary ? 'none' : '1px solid #ebedf0',
        background: primary ? '#4f46e5' : '#fff',
        color: primary ? '#fff' : '#0f172a',
        borderRadius: 8,
        fontSize: 11,
        cursor: 'pointer',
        fontWeight: 600,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        transition: 'all 0.15s',
        boxShadow: primary ? '0 1px 2px rgba(79,70,229,0.3)' : 'none',
        ...style,
      }}
      onMouseEnter={(e) => {
        if (primary) {
          e.currentTarget.style.background = '#4338ca'
          e.currentTarget.style.boxShadow = '0 4px 12px rgba(79,70,229,0.3)'
        } else {
          e.currentTarget.style.background = '#fafbfc'
          e.currentTarget.style.borderColor = '#cbd5e1'
        }
        e.currentTarget.style.transform = 'translateY(-1px)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = primary ? '#4f46e5' : '#fff'
        e.currentTarget.style.boxShadow = primary ? '0 1px 2px rgba(79,70,229,0.3)' : 'none'
        e.currentTarget.style.transform = 'none'
        if (!primary) e.currentTarget.style.borderColor = '#ebedf0'
      }}
    >
      {icon}
      {label}
    </button>
  )
}
