import { describe, expect, it } from 'vitest'

import { clean, computeCheckDigit, validateEan13 } from '@/lib/ean13'

const digits = (base: number) =>
  [...'786123456789'].map((d) => String.fromCodePoint(base + Number(d))).join('')
const FULLWIDTH = digits(0xff10)
const ARABIC_INDIC = digits(0x0660)

describe('clean', () => {
  it.each([
    ['786-1234-56789', '786123456789'],
    ['  7861234567898  ', '7861234567898'],
    ['786 1234 5678 98', '7861234567898'],
    ['-786\t123\n456789-', '786123456789'],
    ['', ''],
  ])('%j → %j', (raw, expected) => {
    expect(clean(raw)).toBe(expected)
  })
})

describe('computeCheckDigit', () => {
  it.each([
    ['786123456789', 8],
    ['400638133393', 1],
    ['978030640615', 7],
    ['000000000000', 0],
    ['590123412345', 7],
  ])('%s → %i', (body, expected) => {
    expect(computeCheckDigit(body)).toBe(expected)
  })

  it.each(['12345678901', '1234567890123', '78612345678a', FULLWIDTH])(
    'rejects malformed body %j',
    (body) => {
      expect(() => computeCheckDigit(body)).toThrow('12 ASCII digits')
    },
  )

  it('is stable across repeated calls (no regex state)', () => {
    expect(() => computeCheckDigit('78612345678a')).toThrow('12 ASCII digits')
    expect(computeCheckDigit('786123456789')).toBe(8)
    expect(() => computeCheckDigit('78612345678a')).toThrow('12 ASCII digits')
  })
})

describe('validateEan13', () => {
  it('appends the check digit to 12 digits', () => {
    expect(validateEan13('786123456789')).toEqual({
      ok: true,
      normalized: '7861234567898',
      checkDigit: 8,
    })
  })

  it('accepts 13 digits with a valid check digit and separators', () => {
    expect(validateEan13('786-1234-567898')).toMatchObject({
      ok: true,
      normalized: '7861234567898',
    })
  })

  it('keeps leading zeros', () => {
    expect(validateEan13('000000000000')).toMatchObject({ normalized: '0000000000000' })
  })

  it('reports the expected check digit with the backend message', () => {
    expect(validateEan13('7861234567897')).toEqual({
      ok: false,
      code: 'INVALID_CHECK_DIGIT',
      message: 'El dígito de control debe ser 8.',
      expectedCheckDigit: 8,
    })
  })

  it.each(['78612345678A', '786.123.456.789', '78612345678²', ARABIC_INDIC, 'abc'])(
    'rejects non-ASCII-digit characters in %j',
    (raw) => {
      expect(validateEan13(raw)).toMatchObject({ ok: false, code: 'INVALID_CHARACTERS' })
    },
  )

  it.each([
    ['', 0],
    ['   ', 0],
    ['78612345678', 11],
    ['78612345678981', 14],
  ])('rejects %j because it has %i digits', (raw, length) => {
    expect(validateEan13(raw)).toEqual({
      ok: false,
      code: 'INVALID_LENGTH',
      message: `El código debe tener 12 o 13 dígitos; tiene ${String(length)}.`,
    })
  })
})
