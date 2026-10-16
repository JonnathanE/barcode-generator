/**
 * Scanner legibility checks for custom colors.
 *
 * Barcode scanners read with red light (~630 nm), so what they "see" is roughly
 * the red channel: red, orange or yellow bars look like the background. We
 * estimate ISO/IEC 15416 Symbol Contrast on the linear red channel:
 * SC = R_background - R_bars (absolute reflectance difference, 0–1). The
 * standard grades SC >= 0.70 as A and >= 0.40 as the minimum; we warn below 0.5.
 * Absolute, not relative: black on a very dark background has no usable contrast.
 */

export const MIN_SYMBOL_CONTRAST = 0.5

export type ContrastWarning = 'LOW_CONTRAST' | 'LIGHT_BACKGROUND_ASSUMED'

function redReflectance(hex: string): number {
  const red = Number.parseInt(hex.slice(1, 3), 16) / 255
  // sRGB → linear light, so the value is proportional to reflected light.
  return red <= 0.04045 ? red / 12.92 : ((red + 0.055) / 1.055) ** 2.4
}

export function symbolContrast(barColor: string, backgroundColor: string): number {
  return Math.max(0, redReflectance(backgroundColor) - redReflectance(barColor))
}

export function contrastWarnings(
  barColor: string,
  background: { kind: 'color' | 'transparent'; color: string },
): ContrastWarning[] {
  // Transparent: the final background is unknown; judge the bars against white.
  const backgroundColor = background.kind === 'transparent' ? '#FFFFFF' : background.color
  const warnings: ContrastWarning[] = []
  if (symbolContrast(barColor, backgroundColor) < MIN_SYMBOL_CONTRAST) warnings.push('LOW_CONTRAST')
  if (background.kind === 'transparent') warnings.push('LIGHT_BACKGROUND_ASSUMED')
  return warnings
}
