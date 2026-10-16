import { z } from 'zod'

import { barcodeOptionsSchema, DEFAULT_OPTIONS } from '@/lib/barcode-options'
import { validateCode } from '@/lib/code-validators'

export const singleFormSchema = barcodeOptionsSchema
  .extend({
    symbology: z.string(),
    code: z.string().max(64, 'El código es demasiado largo.'),
  })
  .superRefine((values, ctx) => {
    const result = validateCode(values.symbology, values.code)
    if (!result.ok) ctx.addIssue({ code: 'custom', path: ['code'], message: result.message })
  })

export type SingleFormValues = z.infer<typeof singleFormSchema>

export const SINGLE_DEFAULTS: SingleFormValues = {
  symbology: 'ean13',
  code: '',
  ...DEFAULT_OPTIONS,
}

/** Preview DPI: resolution doesn't change how the code looks, and it's faster. */
export const PREVIEW_DPI = 150
