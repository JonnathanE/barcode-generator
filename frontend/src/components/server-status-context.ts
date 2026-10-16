import { createContext, useContext } from 'react'

export type ServerState = 'checking' | 'waking' | 'ready' | 'unavailable'

export interface ServerStatusValue {
  state: ServerState
  version: string | undefined
  retry: () => void
}

export const ServerStatusContext = createContext<ServerStatusValue | null>(null)

export function useServerStatus(): ServerStatusValue {
  const value = useContext(ServerStatusContext)
  if (!value) throw new Error('useServerStatus must be used inside <ServerStatusProvider>')
  return value
}

/** Generate buttons stay disabled until the backend answered /health. */
export function useServerReady(): boolean {
  return useServerStatus().state === 'ready'
}
