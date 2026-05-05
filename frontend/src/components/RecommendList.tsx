import { useQuery } from '@tanstack/react-query'
import { recommend } from '@/lib/api'
import { Skeleton } from '@/components/ui/skeleton'
import { RecommendCard } from './RecommendCard'

interface Props {
  itemCode: string
  topK?: number
}

export function RecommendList({ itemCode, topK = 5 }: Props) {
  const { data, isFetching, error } = useQuery({
    queryKey: ['recommend', itemCode, topK],
    queryFn: () => recommend({ item_code: itemCode, top_k: topK }),
    enabled: Boolean(itemCode),
  })

  if (error) {
    return (
      <p className="text-sm text-destructive">
        추천 실패: {(error as Error).message}
      </p>
    )
  }

  if (isFetching || !data) {
    return (
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: topK }).map((_, i) => (
          <Skeleton key={i} className="h-96 w-full" />
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-sm text-muted-foreground">
        <span>
          매칭 풀{' '}
          <span className="font-medium text-foreground tabular-nums">
            {data.matched_count}
          </span>{' '}
          BRN
        </span>
        <span>
          SR 보유율{' '}
          <span className="font-medium text-foreground tabular-nums">
            {data.sr_coverage_pct.toFixed(1)}%
          </span>
        </span>
        <span>
          추천{' '}
          <span className="font-medium text-foreground tabular-nums">
            top {data.recommendations.length}
          </span>
        </span>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {data.recommendations.map((r) => (
          <RecommendCard key={r.brn} item={r} />
        ))}
      </div>
    </div>
  )
}
