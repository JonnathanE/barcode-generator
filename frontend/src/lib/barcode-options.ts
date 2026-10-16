import { z } from 'zod'

import type { RenderOptions } from '@/api/client'

/** RF-05 limits; the backend validates the same ranges. */
export const SCALES = [1, 2, 3, 4, 5] as const
export const DPIS = [150, 300, 600] as const
export const GS1_MAX_SCALE = 2
export const MODULE_MM = 0.33

const HEX_COLOR = /^#[0-9a-fA-F]{6}$/

export const barcodeOptionsSchema = z.object({
  include_text: z.boolean(),
  scale: z.number().int().min(1).max(5),
  bar_height_mm: z
    .number({ error: 'Ingresa una altura en milímetros.' })
    .min(10, 'La altura mínima es 10 mm.')
    .max(50, 'La altura máxima es 50 mm.'),
  dpi: z.union([z.literal(150), z.literal(300), z.literal(600)]),
  bar_color: z.string().regex(HEX_COLOR, 'Usa un color en formato #RRGGBB.'),
  background_kind: z.enum(['color', 'transparent']),
  background_color: z.string().regex(HEX_COLOR, 'Usa un color en formato #RRGGBB.'),
})

export type BarcodeOptionsValues = z.infer<typeof barcodeOptionsSchema>

// Lowercase: the canonical value of <input type="color">, which replaces anything
// it doesn't consider a valid color with black.
export const DEFAULT_OPTIONS: BarcodeOptionsValues = {
  include_text: true,
  scale: 2,
  bar_height_mm: 22.85,
  dpi: 300,
  bar_color: '#000000',
  background_kind: 'color',
  background_color: '#ffffff',
}

export function toApiOptions(values: BarcodeOptionsValues): RenderOptions {
  return {
    include_text: values.include_text,
    scale: values.scale,
    bar_height_mm: values.bar_height_mm,
    dpi: values.dpi,
    bar_color: values.bar_color.toUpperCase(),
    background:
      values.background_kind === 'transparent'
        ? 'transparent'
        : values.background_color.toUpperCase(),
  }
}

/** Approximate printed width (bars + quiet zones + ">" guard) for the UI hint. */
export function approximateWidthMm(scale: number, includeText: boolean): number {
  return (includeText ? 114 : 113) * MODULE_MM * scale
}
