import { keepPreviousData, useQuery } from '@tanstack/react-query'

import {
  type BatchLimits,
  getBatchLimits,
  type OutputFormat,
  type RenderOptions,
} from '@/api/client'
import { useServerReady } from '@/components/server-status-context'
import { useDebouncedValue } from '@/hooks/use-debounced-value'

interface LimitsRequest {
  symbology: string
  formats: OutputFormat[]
  options: RenderOptions
}

/** RF-19: max rows for the chosen formats and options (large PNGs lower it). */
export function useBatchLimits(request: LimitsRequest | null): BatchLimits | undefined {
  const ready = useServerReady()
  const key = useDebouncedValue(request ? JSON.stringify(request) : null, 300)
  const { data } = useQuery({
    queryKey: ['batch-limits', key],
    queryFn: ({ signal }) => {
      const { symbology, formats, options } = JSON.parse(key ?? '') as LimitsRequest
      return getBatchLimits(symbology, { formats, options }, signal)
    },
    enabled: ready && key !== null,
    placeholderData: keepPreviousData,
    staleTime: Number.POSITIVE_INFINITY,
  })
  return data
}
