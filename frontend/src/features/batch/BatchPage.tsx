import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { DownloadIcon, FileDownIcon, LoaderCircleIcon } from 'lucide-react'
import { useState } from 'react'
import { Controller, FormProvider, useForm, useWatch } from 'react-hook-form'
import { toast } from 'sonner'

import {
  ApiError,
  downloadTemplate,
  generateBatch,
  type OutputFormat,
  validateBatch,
} from '@/api/client'
import { BarcodeOptions } from '@/components/BarcodeOptions'
import { SymbologySelect } from '@/components/SymbologySelect'
import { useServerReady } from '@/components/server-status-context'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from '@/components/ui/field'
import { Switch } from '@/components/ui/switch'
import { BatchErrorAlert } from '@/features/batch/BatchErrorAlert'
import { BatchResultsTable } from '@/features/batch/BatchResultsTable'
import { FileDropzone } from '@/features/batch/FileDropzone'
import { GenerationProgress } from '@/features/batch/GenerationProgress'
import {
  BATCH_DEFAULTS,
  type BatchFormValues,
  batchFormSchema,
  DEFAULT_MAX_UPLOAD_MB,
} from '@/features/batch/schema'
import { useBatchLimits } from '@/features/batch/useBatchLimits'
import { ValidationSummary } from '@/features/batch/ValidationSummary'
import { useSymbologies } from '@/hooks/use-symbologies'
import { toApiOptions } from '@/lib/barcode-options'
import { saveBlob } from '@/lib/download'

const FORMAT_OPTIONS: { value: OutputFormat; label: string }[] = [
  { value: 'png', label: 'PNG' },
  { value: 'eps', label: 'EPS vectorial' },
]

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : 'Ocurrió un error inesperado.'
}

export function BatchPage() {
  const form = useForm<BatchFormValues>({
    resolver: zodResolver(batchFormSchema),
    defaultValues: BATCH_DEFAULTS,
    mode: 'onChange',
  })
  const { control, formState } = form
  const values = useWatch({ control })
  const symbologies = useSymbologies()
  const serverReady = useServerReady()
  const [file, setFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)

  const parsed = batchFormSchema.safeParse(values)
  const symbology = values.symbology ?? BATCH_DEFAULTS.symbology
  const restoreLeadingZeros = values.restore_leading_zeros ?? false

  const limits = useBatchLimits(
    parsed.success
      ? {
          symbology: parsed.data.symbology,
          formats: parsed.data.formats,
          options: toApiOptions(parsed.data),
        }
      : null,
  )
  const maxMb = limits?.max_upload_mb ?? DEFAULT_MAX_UPLOAD_MB

  const validation = useMutation({
    mutationFn: (input: { file: File; symbology: string; restoreLeadingZeros: boolean }) =>
      validateBatch(input.symbology, input),
  })
  const report = validation.data

  const generation = useMutation({
    mutationFn: (input: BatchFormValues & { file: File }) =>
      generateBatch(input.symbology, {
        file: input.file,
        restoreLeadingZeros: input.restore_leading_zeros,
        formats: input.formats,
        options: toApiOptions(input),
      }),
    onSuccess: ({ blob, filename }) => {
      saveBlob(blob, filename)
      toast.success(`Descargado ${filename}`)
    },
    onError: (error) => {
      toast.error('No se pudo generar el ZIP', { description: errorMessage(error) })
    },
  })

  const template = useMutation({
    mutationFn: () => downloadTemplate(),
    onSuccess: ({ blob, filename }) => {
      saveBlob(blob, filename)
    },
    onError: (error) => {
      toast.error('No se pudo descargar la plantilla', { description: errorMessage(error) })
    },
  })

  function validate(next: { file?: File | null; symbology?: string; restore?: boolean } = {}) {
    const target = next.file === undefined ? file : next.file
    if (!target) return
    generation.reset()
    validation.mutate({
      file: target,
      symbology: next.symbology ?? symbology,
      restoreLeadingZeros: next.restore ?? restoreLeadingZeros,
    })
  }

  const validCount = report?.summary.valid ?? 0
  const overLimit = limits !== undefined && validCount > limits.max_rows
  let blockedReason: string | null = null
  if (!serverReady) blockedReason = 'Esperando al servidor…'
  else if (!file) blockedReason = 'Sube un archivo de Excel.'
  else if (validation.isPending) blockedReason = 'Validando el archivo…'
  else if (!report) blockedReason = 'Valida el archivo primero.'
  else if (validCount === 0) blockedReason = 'No hay filas válidas para generar.'
  else if (!parsed.success) blockedReason = 'Revisa los formatos y las opciones.'
  else if (overLimit)
    blockedReason =
      `Con estas opciones (PNG de ${String(limits.png_width_px)} x ${String(limits.png_height_px)} px) ` +
      `el máximo es ${String(limits.max_rows)} códigos por lote y tienes ${String(validCount)}. ` +
      'Reduce la escala o el DPI, o genera solo EPS.'

  return (
    <FormProvider {...form}>
      <form
        noValidate
        onSubmit={(event) => {
          event.preventDefault()
          if (parsed.success && file && !blockedReason) generation.mutate({ ...parsed.data, file })
        }}
        className="flex flex-col gap-6"
      >
        <Card>
          <CardHeader>
            <CardTitle>
              <h2>1. Prepara tu Excel</h2>
            </CardTitle>
            <CardDescription>
              Una columna «codigo» con un código por fila y, si quieres, «nombre_archivo» para
              nombrar cada archivo.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              type="button"
              variant="outline"
              disabled={!serverReady || template.isPending}
              onClick={() => {
                template.mutate()
              }}
            >
              <FileDownIcon aria-hidden="true" />
              Descargar plantilla
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>
              <h2>2. Sube y valida</h2>
            </CardTitle>
            <CardDescription>
              Revisamos cada fila antes de generar nada. Hasta {limits?.max_rows ?? 500} códigos por
              lote.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="grid gap-4 sm:grid-cols-[10rem_minmax(0,1fr)] sm:items-end">
              <Controller
                control={control}
                name="symbology"
                render={({ field }) => (
                  <Field>
                    <FieldLabel htmlFor="batch-symbology">Simbología</FieldLabel>
                    <SymbologySelect
                      id="batch-symbology"
                      value={field.value}
                      onChange={(value) => {
                        field.onChange(value)
                        validate({ symbology: value })
                      }}
                      symbologies={symbologies}
                    />
                  </Field>
                )}
              />
              <Controller
                control={control}
                name="restore_leading_zeros"
                render={({ field }) => (
                  <Field orientation="horizontal">
                    <Switch
                      id="batch-restore"
                      checked={field.value}
                      onCheckedChange={(checked) => {
                        field.onChange(checked)
                        validate({ restore: checked })
                      }}
                      aria-describedby="batch-restore-help"
                    />
                    <div>
                      <FieldLabel htmlFor="batch-restore">Restaurar ceros iniciales</FieldLabel>
                      <FieldDescription id="batch-restore-help">
                        Excel quita los ceros a la izquierda de las celdas numéricas: completa a 13
                        dígitos los números de 11 o 12.
                      </FieldDescription>
                    </div>
                  </Field>
                )}
              />
            </div>

            <FileDropzone
              file={file}
              maxMb={maxMb}
              disabled={!serverReady || validation.isPending || generation.isPending}
              onFile={(selected) => {
                setFile(selected)
                setFileError(null)
                validate({ file: selected })
              }}
              onClear={() => {
                setFile(null)
                validation.reset()
                generation.reset()
              }}
              onReject={(message) => {
                setFileError(message)
              }}
            />
            {!serverReady && (
              <p className="text-muted-foreground text-sm">
                La carga se habilita cuando el servidor esté listo.
              </p>
            )}

            <div aria-live="polite" className="flex flex-col gap-4 empty:hidden">
              {fileError && (
                <BatchErrorAlert
                  error={new ApiError('INVALID_FILE_TYPE', fileError)}
                  fallbackTitle="Archivo no válido"
                />
              )}
              {validation.isPending && (
                <p className="text-muted-foreground flex items-center gap-2 text-sm">
                  <LoaderCircleIcon aria-hidden="true" className="size-4 animate-spin" />
                  Validando el archivo…
                </p>
              )}
              {validation.isError && (
                <BatchErrorAlert error={validation.error} fallbackTitle="No se pudo validar" />
              )}
              {report && <ValidationSummary summary={report.summary} />}
            </div>
            {report && report.rows.length > 0 && <BatchResultsTable rows={report.rows} />}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>
              <h2>3. Genera los archivos</h2>
            </CardTitle>
            <CardDescription>
              Se generan solo las filas válidas y descargas un ZIP con png/, eps/ y reporte.csv.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <FieldGroup>
              <Controller
                control={control}
                name="formats"
                render={({ field }) => (
                  <FieldSet data-invalid={Boolean(formState.errors.formats)}>
                    <FieldLegend variant="label">Formatos</FieldLegend>
                    <div className="flex flex-wrap gap-4">
                      {FORMAT_OPTIONS.map(({ value, label }) => (
                        <Field key={value} orientation="horizontal" className="w-auto">
                          <Checkbox
                            id={`batch-format-${value}`}
                            checked={field.value.includes(value)}
                            onCheckedChange={(checked) => {
                              field.onChange(
                                checked === true
                                  ? FORMAT_OPTIONS.map((f) => f.value).filter(
                                      (f) => f === value || field.value.includes(f),
                                    )
                                  : field.value.filter((f) => f !== value),
                              )
                            }}
                          />
                          <FieldLabel htmlFor={`batch-format-${value}`}>{label}</FieldLabel>
                        </Field>
                      ))}
                    </div>
                    <FieldError errors={[formState.errors.formats]} />
                  </FieldSet>
                )}
              />
              <BarcodeOptions idPrefix="batch" />

              <div className="flex flex-col gap-3">
                <Button
                  type="submit"
                  size="lg"
                  className="self-start"
                  disabled={blockedReason !== null || generation.isPending}
                  aria-describedby={blockedReason ? 'batch-generate-blocked' : undefined}
                >
                  {generation.isPending ? (
                    <LoaderCircleIcon aria-hidden="true" className="animate-spin" />
                  ) : (
                    <DownloadIcon aria-hidden="true" />
                  )}
                  {validCount > 0
                    ? `Generar ${String(validCount)} ${validCount === 1 ? 'código' : 'códigos'}`
                    : 'Generar'}
                </Button>
                {blockedReason && !generation.isPending && (
                  <p
                    id="batch-generate-blocked"
                    className={
                      overLimit ? 'text-destructive text-sm' : 'text-muted-foreground text-sm'
                    }
                  >
                    {blockedReason}
                  </p>
                )}
                {generation.isPending && <GenerationProgress count={validCount} />}
                {generation.isError && (
                  <BatchErrorAlert error={generation.error} fallbackTitle="No se pudo generar" />
                )}
              </div>
            </FieldGroup>
          </CardContent>
        </Card>
      </form>
    </FormProvider>
  )
}
