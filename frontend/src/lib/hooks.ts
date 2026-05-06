import { useQuery, useMutation } from '@tanstack/react-query'
import { useState, useEffect, useCallback } from 'react'
import { fetchKeywords, fetchMeta, fetchRecommendV2 } from './api'
import type { RecommendV2Request } from './types'

// ── LocalStorage hook ─────────────────────────────────────────────
export function useLocalStorage<T>(key: string, defaultValue: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = localStorage.getItem(key)
      return stored !== null ? (JSON.parse(stored) as T) : defaultValue
    } catch {
      return defaultValue
    }
  })

  const set = useCallback(
    (next: T | ((prev: T) => T)) => {
      setValue((prev) => {
        const resolved = typeof next === 'function' ? (next as (p: T) => T)(prev) : next
        try {
          localStorage.setItem(key, JSON.stringify(resolved))
        } catch {
          /* noop */
        }
        return resolved
      })
    },
    [key],
  )

  useEffect(() => {
    const handler = (e: StorageEvent) => {
      if (e.key === key && e.newValue !== null) {
        try {
          setValue(JSON.parse(e.newValue) as T)
        } catch {
          /* noop */
        }
      }
    }
    window.addEventListener('storage', handler)
    return () => window.removeEventListener('storage', handler)
  }, [key])

  return [value, set] as const
}

// ── API hooks ─────────────────────────────────────────────────────
export function useKeywords() {
  return useQuery({
    queryKey: ['keywords'],
    queryFn: fetchKeywords,
    staleTime: 5 * 60 * 1000,
  })
}

export function useMeta() {
  return useQuery({
    queryKey: ['meta'],
    queryFn: fetchMeta,
    staleTime: 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  })
}

export function useRecommend() {
  return useMutation({
    mutationFn: (req: RecommendV2Request) => fetchRecommendV2(req),
  })
}
