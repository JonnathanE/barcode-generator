import type { BatchRowStatus } from '@/api/client'

export const STATUS_LABELS: Record<BatchRowStatus, string> = {
  ok: 'Válido',
  error: 'Con error',
  duplicado: 'Duplicado',
}

/** Row background: errors and duplicates stand out, never by color alone (icon + text). */
export const ROW_TINT: Record<BatchRowStatus, string> = {
  ok: '',
  error: 'bg-destructive/5 hover:bg-destructive/10',
  duplicado: 'bg-amber-500/5 hover:bg-amber-500/10',
}
