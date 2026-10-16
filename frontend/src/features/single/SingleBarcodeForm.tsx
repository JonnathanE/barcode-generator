import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { DownloadIcon, LoaderCircleIcon } from 'lucide-react'
import { Controller, FormProvider, useForm, useWatch } from 'react-hook-form'
import { toast } from 'sonner'

import { ApiError, type OutputFormat, renderBarcode } from '@/api/client'
import { BarcodeOptions } from '@/components/BarcodeOptions'
import { SymbologySelect } from '@/components/SymbologySelect'
import { useServerReady, useServerStatus } from '@/components/server-status-context'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { BarcodePreview } from '@/features/single/BarcodePreview'
import {
  PREVIEW_DPI,
  SINGLE_DEFAULTS,
  type SingleFormValues,
  singleFormSchema,
} from '@/features/single/schema'
import { useBarcodePreview } from '@/features/single/useBarcodePreview'
import { useSymbologies } from '@/hooks/use-symbologies'
import { toApiOptions } from '@/lib/barcode-options'
import { validateCode } from '@/lib/code-validators'
import { saveBlob } from '@/lib/download'

const FORMAT_LABELS: Record<OutputFormat, string> = { png: 'PNG', eps: 'EPS vectorial' }

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : 'Ocurrió un error inesperado.'
}

export function SingleBarcodeForm() {
  const form = useForm<SingleFormValues>({
    resolver: zodResolver(singleFormSchema),
    defaultValues: SINGLE_DEFAULTS,
    mode: 'onChange',
  })
  const { control, register, formState } = form
  const values = useWatch({ control })
  const symbologies = useSymbologies()
  const serverReady = useServerReady()
  const { state: serverState } = useServerStatus()

  const parsed = singleFormSchema.safeParse(values)
  const codeCheck = validateCode(values.symbology ?? 'ean13', values.code ?? '')
  const symbology = symbologies.find((s) => s.id === values.symbology) ?? symbologies[0]

  const preview = useBarcodePreview(
    parsed.success
      ? {
          symbology: parsed.data.symbology,
          body: {
            code: parsed.data.code,
            format: 'png',
            options: { ...toApiOptions(parsed.data), dpi: PREVIEW_DPI },
          },
        }
      : null,
  )

  const download = useMutation({
    mutationFn: (format: OutputFormat) => {
      if (!parsed.success) throw new Error('invalid form')
      return renderBarcode(parsed.data.symbology, {
        code: parsed.data.code,
        format,
        options: toApiOptions(parsed.data),
      })
    },
    onSuccess: ({ blob, filename }) => {
      saveBlob(blob, filename)
      toast.success(`Descargado ${filename}`)
    },
    onError: (error) => {
      toast.error('No se pudo descargar', { description: errorMessage(error) })
    },
  })

  const codeError = formState.errors.code?.message
  const showCodeError = Boolean(codeError) && Boolean(formState.dirtyFields.code)
  const canDownload = serverReady && parsed.success && !download.isPending

  let previewMessage: string | null = null
  if (!parsed.success && values.code) previewMessage = 'Corrige los datos para ver la vista previa.'
  else if (parsed.success && !serverReady)
    previewMessage =
      serverState === 'unavailable' ? 'El servidor no está disponible.' : 'Esperando al servidor…'
  else if (parsed.success && preview.error && !preview.isWaiting)
    previewMessage = errorMessage(preview.error)

  return (
    <FormProvider {...form}>
      <form
        noValidate
        onSubmit={(event) => {
          event.preventDefault()
        }}
        className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]"
      >
        <Card>
          <CardHeader>
            <CardTitle>
              <h2>Generar un código</h2>
            </CardTitle>
            <CardDescription>
              Escribe 12 dígitos y se calcula el de control, o 13 y se verifica.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <FieldGroup>
              <div className="grid gap-4 sm:grid-cols-[10rem_minmax(0,1fr)]">
                <Controller
                  control={control}
                  name="symbology"
                  render={({ field }) => (
                    <Field>
                      <FieldLabel htmlFor="single-symbology">Simbología</FieldLabel>
                      <SymbologySelect
                        id="single-symbology"
                        value={field.value}
                        onChange={field.onChange}
                        symbologies={symbologies}
                      />
                    </Field>
                  )}
                />
                <Field data-invalid={showCodeError}>
                  <FieldLabel htmlFor="single-code">Código</FieldLabel>
                  <Input
                    id="single-code"
                    inputMode="numeric"
                    autoComplete="off"
                    spellCheck={false}
                    placeholder="786123456789"
                    className="font-mono"
                    aria-invalid={showCodeError}
                    aria-describedby="single-code-feedback"
                    {...register('code')}
                  />
                  {/* Always mounted so screen readers announce changes (RNF-22). */}
                  <FieldDescription
                    id="single-code-feedback"
                    aria-live="polite"
                    className={showCodeError ? 'text-destructive' : undefined}
                  >
                    {showCodeError
                      ? codeError
                      : codeCheck.ok
                        ? `Código completo: ${codeCheck.normalized}`
                        : 'Se ignoran espacios y guiones.'}
                  </FieldDescription>
                </Field>
              </div>
              <BarcodeOptions idPrefix="single" />
            </FieldGroup>
          </CardContent>
        </Card>

        <Card className="lg:sticky lg:top-6 lg:self-start">
          <CardHeader>
            <CardTitle>
              <h2>Vista previa</h2>
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <BarcodePreview
              imageUrl={preview.imageUrl}
              alt={
                parsed.success ? `Código de barras ${codeCheck.ok ? codeCheck.normalized : ''}` : ''
              }
              isWaiting={preview.isWaiting}
              transparent={values.background_kind === 'transparent'}
              message={previewMessage}
            />
            <div className="flex flex-wrap gap-2">
              {(symbology?.formats ?? ['png', 'eps'])
                .toSorted((a, b) => b.localeCompare(a))
                .map((format) => (
                  <Button
                    key={format}
                    type="button"
                    disabled={!canDownload}
                    onClick={() => {
                      download.mutate(format)
                    }}
                  >
                    {download.isPending && download.variables === format ? (
                      <LoaderCircleIcon aria-hidden="true" className="animate-spin" />
                    ) : (
                      <DownloadIcon aria-hidden="true" />
                    )}
                    Descargar {FORMAT_LABELS[format]}
                  </Button>
                ))}
            </div>
            {!serverReady && (
              <p className="text-muted-foreground text-sm">
                Las descargas se habilitan cuando el servidor esté listo.
              </p>
            )}
          </CardContent>
        </Card>
      </form>
    </FormProvider>
  )
}
