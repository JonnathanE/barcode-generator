import { describe, expect, it } from 'vitest'

import {
  approximateWidthMm,
  barcodeOptionsSchema,
  DEFAULT_OPTIONS,
  toApiOptions,
} from '@/lib/barcode-options'

describe('barcodeOptionsSchema', () => {
  it('accepts the defaults', () => {
    expect(barcodeOptionsSchema.parse(DEFAULT_OPTIONS)).toEqual(DEFAULT_OPTIONS)
  })

  it.each([
    [{ bar_height_mm: 9.9 }, 'La altura mínima es 10 mm.'],
    [{ bar_height_mm: 50.1 }, 'La altura máxima es 50 mm.'],
    [{ bar_color: 'red' }, 'Usa un color en formato #RRGGBB.'],
  ])('rejects %j', (override, message) => {
    const result = barcodeOptionsSchema.safeParse({ ...DEFAULT_OPTIONS, ...override })

    expect(result.success).toBe(false)
    expect(result.error?.issues[0]?.message).toBe(message)
  })
})

describe('toApiOptions', () => {
  it('maps a solid background to an uppercase hex', () => {
    expect(
      toApiOptions({ ...DEFAULT_OPTIONS, bar_color: '#1f3a93', background_color: '#fff8dc' }),
    ).toMatchObject({ bar_color: '#1F3A93', background: '#FFF8DC' })
  })

  it('maps the transparent background', () => {
    expect(toApiOptions({ ...DEFAULT_OPTIONS, background_kind: 'transparent' }).background).toBe(
      'transparent',
    )
  })
})

it('approximateWidthMm matches the backend extent (114 modules with text)', () => {
  expect(approximateWidthMm(1, true)).toBeCloseTo(37.62)
  expect(approximateWidthMm(2, false)).toBeCloseTo(74.58)
})
