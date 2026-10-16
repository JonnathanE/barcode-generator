/**
 * Client-side mirror of backend/app/domain/ean13.py (RF-01 to RF-03, RF-07).
 * The backend is the source of truth; messages are kept identical.
 */

export const BODY_LENGTH = 12
export const FULL_LENGTH = 13

const SEPARATORS = /[\s-]+/g
// ASCII only, like the backend: "²" or Arabic-Indic digits are not valid.
const HAS_NON_DIGIT = /[^0-9]/

export type Ean13ErrorCode = 'INVALID_CHARACTERS' | 'INVALID_LENGTH' | 'INVALID_CHECK_DIGIT'

export type Ean13Result =
  | { ok: true; normalized: string; checkDigit: number }
  | { ok: false; code: Ean13ErrorCode; message: string; expectedCheckDigit?: number }

/** Remove spaces and hyphens anywhere in the input (RF-03). */
export function clean(raw: string): string {
  return raw.replace(SEPARATORS, '')
}

/** GS1 mod-10 check digit: weights 1, 3, 1, 3… from the left. */
export function computeCheckDigit(body: string): number {
  if (body.length !== BODY_LENGTH || HAS_NON_DIGIT.test(body)) {
    throw new Error('body must be exactly 12 ASCII digits')
  }
  let total = 0
  for (let index = 0; index < BODY_LENGTH; index++) {
    total += Number(body[index]) * (index % 2 ? 3 : 1)
  }
  return (10 - (total % 10)) % 10
}

export function validateEan13(raw: string): Ean13Result {
  const code = clean(raw)

  if (HAS_NON_DIGIT.test(code)) {
    return {
      ok: false,
      code: 'INVALID_CHARACTERS',
      message: 'El código solo puede contener dígitos (se permiten espacios y guiones).',
    }
  }

  if (code.length !== BODY_LENGTH && code.length !== FULL_LENGTH) {
    return {
      ok: false,
      code: 'INVALID_LENGTH',
      message: `El código debe tener 12 o 13 dígitos; tiene ${String(code.length)}.`,
    }
  }

  const expected = computeCheckDigit(code.slice(0, BODY_LENGTH))
  if (code.length === BODY_LENGTH) {
    return { ok: true, normalized: `${code}${String(expected)}`, checkDigit: expected }
  }

  if (Number(code[BODY_LENGTH]) !== expected) {
    return {
      ok: false,
      code: 'INVALID_CHECK_DIGIT',
      message: `El dígito de control debe ser ${String(expected)}.`,
      expectedCheckDigit: expected,
    }
  }
  return { ok: true, normalized: code, checkDigit: expected }
}
