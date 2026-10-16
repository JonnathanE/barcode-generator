import { ChevronLeftIcon, ChevronRightIcon } from 'lucide-react'
import { useMemo, useState } from 'react'

import type { BatchRow, BatchRowStatus } from '@/api/client'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { StatusLabel } from '@/features/batch/StatusLabel'
import { ROW_TINT } from '@/features/batch/status'
import { cn } from '@/lib/utils'

export const PAGE_SIZE = 50

type Filter = 'all' | BatchRowStatus

const FILTERS: { value: Filter; label: string }[] = [
  { value: 'all', label: 'Todos' },
  { value: 'ok', label: 'Válidos' },
  { value: 'error', label: 'Con error' },
  { value: 'duplicado', label: 'Duplicados' },
]

const HEADERS = ['Fila', 'Valor original', 'Código', 'Estado', 'Mensaje', 'Archivo']

/** RF-13: per-row report with filters and pagination. */
export function BatchResultsTable({ rows }: { rows: BatchRow[] }) {
  const [filter, setFilter] = useState<Filter>('all')
  const [page, setPage] = useState(0)

  const counts = useMemo(() => {
    const result: Record<Filter, number> = { all: rows.length, ok: 0, error: 0, duplicado: 0 }
    for (const row of rows) result[row.status] += 1
    return result
  }, [rows])
  const visible = useMemo(
    () => (filter === 'all' ? rows : rows.filter((row) => row.status === filter)),
    [rows, filter],
  )
  const pageCount = Math.max(1, Math.ceil(visible.length / PAGE_SIZE))
  const current = Math.min(page, pageCount - 1)
  const pageRows = visible.slice(current * PAGE_SIZE, (current + 1) * PAGE_SIZE)

  return (
    <div className="flex flex-col gap-3">
      <fieldset className="flex flex-wrap gap-2">
        <legend className="sr-only">Filtrar filas</legend>
        {FILTERS.map(({ value, label }) => (
          <Button
            key={value}
            type="button"
            size="sm"
            variant={filter === value ? 'default' : 'outline'}
            aria-pressed={filter === value}
            onClick={() => {
              setFilter(value)
              setPage(0)
            }}
          >
            {label} ({counts[value]})
          </Button>
        ))}
      </fieldset>

      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              {HEADERS.map((header) => (
                <TableHead key={header}>{header}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {pageRows.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={HEADERS.length}
                  className="text-muted-foreground h-16 text-center"
                >
                  No hay filas con este filtro.
                </TableCell>
              </TableRow>
            ) : (
              pageRows.map((row) => (
                <TableRow key={row.row} className={ROW_TINT[row.status]}>
                  <TableCell className="align-top tabular-nums">{row.row}</TableCell>
                  <TableCell className="align-top font-mono">{row.input || '—'}</TableCell>
                  <TableCell className="align-top font-mono">{row.normalized ?? '—'}</TableCell>
                  <TableCell className="align-top">
                    <StatusLabel status={row.status} />
                  </TableCell>
                  <TableCell
                    className={cn(
                      'min-w-56 align-top whitespace-normal',
                      row.status === 'error' && 'text-destructive',
                    )}
                  >
                    {row.message || '—'}
                  </TableCell>
                  <TableCell className="align-top font-mono">{row.filename ?? '—'}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {pageCount > 1 && (
        <nav aria-label="Páginas de la tabla" className="flex items-center justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={current === 0}
            onClick={() => {
              setPage(current - 1)
            }}
          >
            <ChevronLeftIcon aria-hidden="true" />
            Anterior
          </Button>
          <span className="text-muted-foreground text-sm tabular-nums">
            Página {current + 1} de {pageCount}
          </span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={current >= pageCount - 1}
            onClick={() => {
              setPage(current + 1)
            }}
          >
            Siguiente
            <ChevronRightIcon aria-hidden="true" />
          </Button>
        </nav>
      )}
    </div>
  )
}
