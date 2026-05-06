interface Props {
  compareMode: boolean
  onToggleCompare: () => void
  totalCount: number
  showCount: number
}

export function Toolbar({ compareMode, onToggleCompare, totalCount, showCount }: Props) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 8,
        alignItems: 'center',
        marginBottom: 10,
        padding: '8px 12px',
        background: '#fff',
        borderRadius: 10,
        fontSize: 11,
        boxShadow: '0 1px 2px rgba(15,23,42,0.04), 0 1px 3px rgba(15,23,42,0.05)',
      }}
    >
      <ToolbarToggle active={compareMode} onClick={onToggleCompare}>
        비교 보기
      </ToolbarToggle>
      <span
        style={{ marginLeft: 'auto', color: '#94a3b8', fontWeight: 500 }}
      >
        상위 {showCount}건 / 전체 {totalCount}
      </span>
    </div>
  )
}

function ToolbarToggle({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '4px 11px',
        border: `1px solid ${active ? '#0f172a' : '#ebedf0'}`,
        background: active ? '#0f172a' : '#fff',
        color: active ? '#fff' : '#0f172a',
        borderRadius: 6,
        fontSize: 11,
        cursor: 'pointer',
        fontWeight: 500,
        transition: 'all 0.15s',
      }}
    >
      {children}
    </button>
  )
}
