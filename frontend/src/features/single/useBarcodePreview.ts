import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useRef } from 'react'

import { renderBarcode, type RenderRequest } from '@/api/client'
import { useServerReady } from '@/components/server-status-context'
import { useDebouncedValue } from '@/hooks/use-debounced-value'

export interface PreviewRequest {
  symbology: string
  body: RenderRequest
}

export const PREVIEW_DEBOUNCE_MS = 300

/** RF-04: PNG preview, refreshed 300 ms after the last valid change. */
export function useBarcodePreview(request: PreviewRequest | null) {
  const ready = useServerReady()
  // Serialized: a stable primitive for the debounce and the query key.
  const debouncedKey = useDebouncedValue(
    request ? JSON.stringify(request) : null,
    PREVIEW_DEBOUNCE_MS,
  )

  const query = useQuery({
    queryKey: ['preview', debouncedKey],
    queryFn: ({ signal }) => {
      const { symbology, body } = JSON.parse(debouncedKey ?? '') as PreviewRequest
      return renderBarcode(symbology, body, { inline: true, signal })
    },
    enabled: ready && debouncedKey !== null,
    placeholderData: keepPreviousData,
    staleTime: Number.POSITIVE_INFINITY,
    gcTime: 60_000,
  })

  const blob = query.data?.blob
  const imageUrl = useMemo(() => (blob ? URL.createObjectURL(blob) : null), [blob])
  // Free the previous image when a new one arrives. Not in the effect cleanup:
  // StrictMode re-runs effects in development and would revoke the current URL.
  const previousUrl = useRef<string | null>(null)
  useEffect(() => {
    const previous = previousUrl.current
    previousUrl.current = imageUrl
    if (previous && previous !== imageUrl) URL.revokeObjectURL(previous)
  }, [imageUrl])

  const isWaiting =
    request !== null && (JSON.stringify(request) !== debouncedKey || query.isFetching)
  return { imageUrl, error: query.error, isWaiting }
}
