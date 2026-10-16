import { TriangleAlertIcon } from 'lucide-react'

import type { BatchValidateResponse } from '@/api/client'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { cn } from '@/lib/utils'

const TILES = [
  { key: 'total', label: 'Filas', className: '' },
  { key: 'valid', label: 'Válidas', className: 'text-emerald-700 dark:text-emerald-400' },
  { key: 'errors', label: 'Con error', className: 'text-destructive' },
  { key: 'duplicates', label: 'Duplicadas', className: 'text-amber-700 dark:text-amber-400' },
] as const

export function ValidationSummary({ summary }: { summary: BatchValidateResponse['summary'] }) {
  return (
    <div className="flex flex-col gap-3">
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {TILES.map(({ key, label, className }) => (
          <div key={key} className="rounded-lg border p-3">
            <dt className="text-muted-foreground text-sm">{label}</dt>
            <dd className={cn('text-2xl font-semibold tabular-nums', className)}>{summary[key]}</dd>
          </div>
        ))}
      </dl>
      {summary.errors > 0 && (
        <Alert variant="destructive" role="note">
          <TriangleAlertIcon aria-hidden="true" />
          <AlertTitle>
            {summary.errors === 1
              ? '1 fila tiene errores y no se generará'
              : `${String(summary.errors)} filas tienen errores y no se generarán`}
          </AlertTitle>
          <AlertDescription>
            Revisa el mensaje de cada fila, corrígelas en el Excel y vuelve a subir el archivo.
            También puedes continuar y generar solo las filas válidas.
          </AlertDescription>
        </Alert>
      )}
      {summary.duplicates > 0 && (
        <p className="text-muted-foreground text-sm">
          Los códigos repetidos se generan una sola vez.
        </p>
      )}
    </div>
  )
}
