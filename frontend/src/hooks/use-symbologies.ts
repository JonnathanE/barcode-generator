import { useQuery } from '@tanstack/react-query'

import { getSymbologies, type Symbology } from '@/api/client'
import { useServerReady } from '@/components/server-status-context'

/** Shown before the server answers, so the selector never renders empty. */
export const FALLBACK_SYMBOLOGIES: Symbology[] = [
  { id: 'ean13', name: 'EAN-13', formats: ['eps', 'png'] },
]

export function useSymbologies(): Symbology[] {
  const ready = useServerReady()
  const { data } = useQuery({
    queryKey: ['symbologies'],
    queryFn: ({ signal }) => getSymbologies(signal),
    enabled: ready,
    staleTime: Number.POSITIVE_INFINITY,
  })
  return data ?? FALLBACK_SYMBOLOGIES
}
