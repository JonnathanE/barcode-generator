import { TriangleAlertIcon } from 'lucide-react'
import { Controller, useFormContext, useWatch } from 'react-hook-form'

import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import {
  approximateWidthMm,
  type BarcodeOptionsValues,
  DPIS,
  GS1_MAX_SCALE,
  SCALES,
} from '@/lib/barcode-options'
import { contrastWarnings } from '@/lib/contrast'

const WARNING_TEXT = {
  LOW_CONTRAST:
    'Contraste insuficiente para lectores: usa barras oscuras (negro, azul o verde oscuro) sobre un fondo claro. Los lectores usan luz roja, así que barras rojas, naranjas o amarillas no se leen.',
  LIGHT_BACKGROUND_ASSUMED:
    'Fondo transparente: colócalo sobre un fondo claro y respeta el margen blanco a los lados.',
} as const

function Warning({ children }: { children: string }) {
  return (
    <p className="flex gap-2 text-sm text-amber-700 dark:text-amber-400">
      <TriangleAlertIcon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      {children}
    </p>
  )
}

function ColorInput({
  value,
  onChange,
  ...props
}: { value: string; onChange: (value: string) => void } & Omit<
  React.ComponentProps<'input'>,
  'value' | 'onChange' | 'type'
>) {
  return (
    <div className="flex items-center gap-2">
      <Input
        type="color"
        className="h-8 w-14 cursor-pointer p-1"
        value={value}
        onChange={(event) => {
          onChange(event.target.value)
        }}
        {...props}
      />
      <span className="font-mono text-sm uppercase">{value}</span>
    </div>
  )
}

/** RF-05 options, for any form whose values include BarcodeOptionsValues. */
export function BarcodeOptions({ idPrefix = 'options' }: { idPrefix?: string }) {
  const { control, register, formState } = useFormContext<BarcodeOptionsValues>()
  const [scale, includeText, barColor, backgroundKind, backgroundColor] = useWatch({
    control,
    name: ['scale', 'include_text', 'bar_color', 'background_kind', 'background_color'],
  })
  const warnings = contrastWarnings(barColor, { kind: backgroundKind, color: backgroundColor })
  const id = (name: string) => `${idPrefix}-${name}`

  return (
    <FieldSet>
      <FieldLegend>Opciones</FieldLegend>
      <FieldGroup>
        <Controller
          control={control}
          name="include_text"
          render={({ field }) => (
            <Field orientation="horizontal">
              <Switch
                id={id('include-text')}
                checked={field.value}
                onCheckedChange={field.onChange}
              />
              <FieldLabel htmlFor={id('include-text')}>Mostrar los dígitos</FieldLabel>
            </Field>
          )}
        />

        <div className="grid gap-4 sm:grid-cols-2">
          <Controller
            control={control}
            name="scale"
            render={({ field }) => (
              <Field>
                <FieldLabel htmlFor={id('scale')}>Escala</FieldLabel>
                <Select
                  value={String(field.value)}
                  onValueChange={(value) => {
                    field.onChange(Number(value))
                  }}
                >
                  <SelectTrigger id={id('scale')} className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {SCALES.map((value) => (
                      <SelectItem key={value} value={String(value)}>
                        {value} · {value * 100} %
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FieldDescription>
                  Ancho aproximado: {approximateWidthMm(scale, includeText).toFixed(1)} mm
                </FieldDescription>
              </Field>
            )}
          />

          <Field data-invalid={Boolean(formState.errors.bar_height_mm)}>
            <FieldLabel htmlFor={id('bar-height')}>Altura de barras (mm)</FieldLabel>
            <Input
              id={id('bar-height')}
              type="number"
              inputMode="decimal"
              step="0.05"
              min={10}
              max={50}
              aria-invalid={Boolean(formState.errors.bar_height_mm)}
              {...register('bar_height_mm', { valueAsNumber: true })}
            />
            <FieldError errors={[formState.errors.bar_height_mm]} />
          </Field>

          <Controller
            control={control}
            name="dpi"
            render={({ field }) => (
              <Field>
                <FieldLabel htmlFor={id('dpi')}>Resolución del PNG</FieldLabel>
                <Select
                  value={String(field.value)}
                  onValueChange={(value) => {
                    field.onChange(Number(value))
                  }}
                >
                  <SelectTrigger id={id('dpi')} className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {DPIS.map((value) => (
                      <SelectItem key={value} value={String(value)}>
                        {value} DPI
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FieldDescription>El EPS es vectorial y no depende del DPI.</FieldDescription>
              </Field>
            )}
          />

          <Controller
            control={control}
            name="bar_color"
            render={({ field }) => (
              <Field>
                <FieldLabel htmlFor={id('bar-color')}>Color de barras</FieldLabel>
                <ColorInput id={id('bar-color')} value={field.value} onChange={field.onChange} />
              </Field>
            )}
          />
        </div>

        <Controller
          control={control}
          name="background_kind"
          render={({ field }) => (
            <FieldSet>
              <FieldLegend variant="label">Fondo</FieldLegend>
              <RadioGroup
                value={field.value}
                onValueChange={field.onChange}
                className="flex flex-wrap items-center gap-4"
              >
                <Field orientation="horizontal" className="w-auto">
                  <RadioGroupItem value="color" id={id('background-color-kind')} />
                  <FieldLabel htmlFor={id('background-color-kind')}>Color</FieldLabel>
                </Field>
                <Field orientation="horizontal" className="w-auto">
                  <RadioGroupItem value="transparent" id={id('background-transparent')} />
                  <FieldLabel htmlFor={id('background-transparent')}>Transparente</FieldLabel>
                </Field>
                {backgroundKind === 'color' && (
                  <Controller
                    control={control}
                    name="background_color"
                    render={({ field: colorField }) => (
                      <ColorInput
                        aria-label="Color de fondo"
                        value={colorField.value}
                        onChange={colorField.onChange}
                      />
                    )}
                  />
                )}
              </RadioGroup>
            </FieldSet>
          )}
        />

        <div aria-live="polite" className="flex flex-col gap-2 empty:hidden">
          {scale > GS1_MAX_SCALE && (
            <Warning>
              Escala fuera del rango GS1 (80 %–200 %): úsala solo si el empaque lo exige.
            </Warning>
          )}
          {warnings.map((warning) => (
            <Warning key={warning}>{WARNING_TEXT[warning]}</Warning>
          ))}
        </div>
      </FieldGroup>
    </FieldSet>
  )
}
