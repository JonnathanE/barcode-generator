import { RefreshCwIcon } from 'lucide-react'

import { type ServerState, useServerStatus } from '@/components/server-status-context'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const LABELS: Record<ServerState, string> = {
  checking: 'Comprobando servidor…',
  waking: 'Iniciando servidor (puede tardar hasta 1 minuto)…',
  ready: 'Servidor listo',
  unavailable: 'Servidor no disponible',
}

const DOT: Record<ServerState, string> = {
  checking: 'bg-muted-foreground animate-pulse',
  waking: 'bg-amber-500 animate-pulse',
  ready: 'bg-emerald-500',
  unavailable: 'bg-destructive',
}

export function ServerStatus() {
  const { state, retry } = useServerStatus()

  return (
    <div className="flex items-center gap-2 text-sm">
      {/* Announced by screen readers when the state changes (RNF-22). */}
      <output aria-live="polite" className="text-muted-foreground flex items-center gap-2">
        <span aria-hidden="true" className={cn('size-2 shrink-0 rounded-full', DOT[state])} />
        {LABELS[state]}
      </output>
      {state === 'unavailable' && (
        <Button variant="outline" size="sm" onClick={retry}>
          <RefreshCwIcon aria-hidden="true" />
          Reintentar
        </Button>
      )}
    </div>
  )
}
