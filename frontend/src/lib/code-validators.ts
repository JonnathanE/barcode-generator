import { clean, validateEan13 } from '@/lib/ean13'

export type CodeValidation = { ok: true; normalized: string } | { ok: false; message: string }

type Validator = (raw: string) => CodeValidation

/**
 * Client-side validators by symbology id (RF-07). A symbology without one is
 * validated only by the backend.
 */
const VALIDATORS: Record<string, Validator> = {
  ean13: (raw) => {
    if (clean(raw) === '') return { ok: false, message: 'Ingresa un código de 12 o 13 dígitos.' }
    const result = validateEan13(raw)
    return result.ok ? result : { ok: false, message: result.message }
  },
}

export function validateCode(symbology: string, raw: string): CodeValidation {
  const validator = VALIDATORS[symbology]
  if (validator) return validator(raw)
  return raw.trim()
    ? { ok: true, normalized: raw.trim() }
    : { ok: false, message: 'Ingresa un código.' }
}
