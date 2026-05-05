import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listItems } from '@/lib/api'
import type { ItemSummary } from '@/lib/types'
import { Input } from '@/components/ui/input'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

interface Props {
  selected: ItemSummary | null
  onSelect: (item: ItemSummary) => void
}

export function ItemSearch({ selected, onSelect }: Props) {
  const [raw, setRaw] = useState('')
  const [debounced, setDebounced] = useState('')

  useEffect(() => {
    const id = setTimeout(() => setDebounced(raw.trim()), 250)
    return () => clearTimeout(id)
  }, [raw])

  const { data, isFetching, error } = useQuery({
    queryKey: ['items', debounced],
    queryFn: () => listItems(debounced, 10),
  })

  return (
    <div className="space-y-3">
      <Input
        placeholder="품명 또는 세부품명번호 (예: 수중펌프, 4921...)"
        value={raw}
        onChange={(e) => setRaw(e.target.value)}
      />

      {error ? (
        <p className="text-sm text-destructive">검색 실패: {(error as Error).message}</p>
      ) : null}

      {isFetching ? (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : (
        <ul className="space-y-1">
          {(data ?? []).map((it) => {
            const isActive = selected?.item_code === it.item_code
            return (
              <li key={it.item_code}>
                <Card
                  onClick={() => onSelect(it)}
                  className={`cursor-pointer p-3 transition hover:bg-accent ${
                    isActive ? 'border-primary ring-1 ring-primary' : ''
                  }`}
                >
                  <div className="flex items-baseline justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium">{it.item_name}</div>
                      <div className="text-xs text-muted-foreground">{it.item_code}</div>
                    </div>
                    <div className="shrink-0 text-xs text-muted-foreground">
                      공고 {it.bid_count}건
                    </div>
                  </div>
                </Card>
              </li>
            )
          })}
          {data && data.length === 0 ? (
            <p className="text-sm text-muted-foreground">결과 없음</p>
          ) : null}
        </ul>
      )}
    </div>
  )
}
