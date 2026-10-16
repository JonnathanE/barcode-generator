import { describe, expect, it } from 'vitest'

import { contrastWarnings, MIN_SYMBOL_CONTRAST, symbolContrast } from '@/lib/contrast'

const white = { kind: 'color' as const, color: '#FFFFFF' }

describe('symbolContrast', () => {
  it('is 1 for black on white and 0 for equal colors', () => {
    expect(symbolContrast('#000000', '#FFFFFF')).toBe(1)
    expect(symbolContrast('#777777', '#777777')).toBe(0)
  })

  it.each([
    ['#1F3A93', 'azul marino'],
    ['#003300', 'verde oscuro'],
    ['#000000', 'negro'],
  ])('dark non-red bars (%s, %s) are readable on white', (bar) => {
    expect(symbolContrast(bar, '#FFFFFF')).toBeGreaterThanOrEqual(MIN_SYMBOL_CONTRAST)
  })

  it.each([
    ['#FF0000', 'rojo'],
    ['#FF8800', 'naranja'],
    ['#FFD700', 'amarillo'],
  ])('red-family bars (%s, %s) are invisible to red-light scanners', (bar) => {
    expect(symbolContrast(bar, '#FFFFFF')).toBeLessThan(MIN_SYMBOL_CONTRAST)
  })

  it('light bars on white and light backgrounds behave as expected', () => {
    expect(symbolContrast('#808080', '#FFFFFF')).toBeGreaterThanOrEqual(MIN_SYMBOL_CONTRAST)
    expect(symbolContrast('#000000', '#FFF8DC')).toBeGreaterThanOrEqual(MIN_SYMBOL_CONTRAST)
    expect(symbolContrast('#C0C0C0', '#FFFFFF')).toBeLessThan(MIN_SYMBOL_CONTRAST)
  })

  it('a dark background is never enough, whatever the bars', () => {
    expect(symbolContrast('#000000', '#1A1A1A')).toBeLessThan(MIN_SYMBOL_CONTRAST)
  })
})

describe('contrastWarnings', () => {
  it('has no warnings for the defaults', () => {
    expect(contrastWarnings('#000000', white)).toEqual([])
  })

  it('warns about low contrast', () => {
    expect(contrastWarnings('#FF0000', white)).toEqual(['LOW_CONTRAST'])
    expect(contrastWarnings('#000000', { kind: 'color', color: '#202040' })).toEqual([
      'LOW_CONTRAST',
    ])
  })

  it('reminds that a transparent background must be light', () => {
    expect(contrastWarnings('#000000', { kind: 'transparent', color: '#000000' })).toEqual([
      'LIGHT_BACKGROUND_ASSUMED',
    ])
  })
})
