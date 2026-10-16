import { useQuery } from '@tanstack/react-query'
import { type ReactNode, useEffect, useMemo, useState } from 'react'

import { getHealth } from '@/api/client'
import { type ServerState, ServerStatusContext } from '@/components/server-status-context'

const backoff = (attempt: number) => Math.min(2_000 * 2 ** attempt, 10_000)

interface ServerStatusProviderProps {
  children: ReactNode
  /** After this long without an answer we tell the user the server is waking up. */
  slowAfterMs?: number
  retry?: number | false
  retryDelayMs?: (attempt: number) => number
}

export function ServerStatusProvider({
  children,
  slowAfterMs = 2_000,
  retry = 3,
  retryDelayMs = backoff,
}: ServerStatusProviderProps) {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => getHealth(signal),
    retry,
    retryDelay: retryDelayMs,
    staleTime: Number.POSITIVE_INFINITY,
    refetchOnWindowFocus: false,
  })

  const [slow, setSlow] = useState(false)
  useEffect(() => {
    const timer = setTimeout(() => {
      setSlow(true)
    }, slowAfterMs)
    return () => {
      clearTimeout(timer)
    }
  }, [slowAfterMs])

  const { data, isFetching, isError, refetch } = health
  const value = useMemo(() => {
    let state: ServerState
    if (data) state = 'ready'
    else if (isFetching) state = slow ? 'waking' : 'checking'
    else if (isError) state = 'unavailable'
    else state = 'checking'
    return {
      state,
      version: data?.version,
      retry: () => {
        void refetch()
      },
    }
  }, [data, isFetching, isError, slow, refetch])

  return <ServerStatusContext value={value}>{children}</ServerStatusContext>
}
