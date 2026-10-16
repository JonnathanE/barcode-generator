import { CheckCircle2Icon, CopyIcon, XCircleIcon } from 'lucide-react'

import type { BatchRowStatus } from '@/api/client'
import { STATUS_LABELS } from '@/features/batch/status'
import { cn } from '@/lib/utils'

const STYLES: Record<BatchRowStatus, { icon: typeof CheckCircle2Icon; className: string }> = {
  ok: { icon: CheckCircle2Icon, className: 'text-emerald-700 dark:text-emerald-400' },
  error: { icon: XCircleIcon, className: 'text-destructive' },
  duplicado: { icon: CopyIcon, className: 'text-amber-700 dark:text-amber-400' },
}

export function StatusLabel({ status }: { status: BatchRowStatus }) {
  const { icon: Icon, className } = STYLES[status]
  return (
    <span
      className={cn('inline-flex items-center gap-1.5 font-medium whitespace-nowrap', className)}
    >
      <Icon aria-hidden="true" className="size-4" />
      {STATUS_LABELS[status]}
    </span>
  )
}
