import { FileSpreadsheetIcon, UploadIcon, XIcon } from 'lucide-react'
import { type DragEvent, useId, useState } from 'react'

import { Button } from '@/components/ui/button'
import { checkExcelFile, formatSize } from '@/features/batch/file-checks'
import { cn } from '@/lib/utils'

interface FileDropzoneProps {
  file: File | null
  maxMb: number
  disabled?: boolean
  onFile: (file: File) => void
  onClear: () => void
  onReject: (message: string) => void
}

/**
 * RF-09: drag and drop or file picker. A <label> around a visually hidden (but
 * focusable) <input type="file"> keeps it keyboard accessible without extra code.
 */
export function FileDropzone({
  file,
  maxMb,
  disabled = false,
  onFile,
  onClear,
  onReject,
}: FileDropzoneProps) {
  const inputId = useId()
  const hintId = useId()
  const [dragging, setDragging] = useState(false)

  function accept(candidate: File | undefined) {
    if (!candidate) return
    const problem = checkExcelFile(candidate, maxMb)
    if (problem) onReject(problem)
    else onFile(candidate)
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault()
    setDragging(false)
    if (!disabled) accept(event.dataTransfer.files[0])
  }

  if (file) {
    return (
      <div className="flex items-center gap-3 rounded-lg border p-3">
        <FileSpreadsheetIcon aria-hidden="true" className="size-8 shrink-0 text-emerald-600" />
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium">{file.name}</p>
          <p className="text-muted-foreground text-sm">{formatSize(file.size)}</p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Quitar archivo"
          disabled={disabled}
          onClick={onClear}
        >
          <XIcon aria-hidden="true" />
        </Button>
      </div>
    )
  }

  return (
    // Drag and drop is a pointer-only enhancement; the file input inside is the accessible path.
    // oxlint-disable-next-line jsx-a11y/no-noninteractive-element-interactions
    <label
      htmlFor={inputId}
      onDragOver={(event) => {
        event.preventDefault()
        if (!disabled) setDragging(true)
      }}
      onDragLeave={() => {
        setDragging(false)
      }}
      onDrop={handleDrop}
      className={cn(
        'flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed p-8 text-center transition-colors',
        'focus-within:border-ring focus-within:ring-ring/50 focus-within:ring-3',
        dragging ? 'border-primary bg-muted' : 'hover:bg-muted/50',
        disabled && 'pointer-events-none opacity-50',
      )}
    >
      <UploadIcon aria-hidden="true" className="text-muted-foreground size-8" />
      <span className="font-medium">Arrastra tu Excel aquí o haz clic para elegirlo</span>
      <span id={hintId} className="text-muted-foreground text-sm">
        Archivo .xlsx de hasta {maxMb} MB. Se lee la primera hoja.
      </span>
      <input
        id={inputId}
        type="file"
        accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        className="sr-only"
        aria-describedby={hintId}
        disabled={disabled}
        onChange={(event) => {
          accept(event.target.files?.[0])
          event.target.value = '' // choosing the same file again fires onChange
        }}
      />
    </label>
  )
}
