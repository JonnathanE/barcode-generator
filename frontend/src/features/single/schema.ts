import * as z from 'zod/mini'

import { barcodeOptionsSchema, DEFAULT_OPTIONS } from '@/lib/barcode-options'
import { validateCode } from '@/lib/code-validators'

export const singleFormSchema = z
  .extend(barcodeOptionsSchema, {
    symbology: z.string(),
    code: z.string().check(z.maxLength(64, 'El código es demasiado largo.')),
  })
  .check(
    z.superRefine((values, ctx) => {
      const result = validateCode(values.symbology, values.code)
      if (!result.ok) {
        ctx.addIssue({
          code: 'custom',
          path: ['code'],
          message: result.message,
          input: values.code,
        })
      }
    }),
  )

export type SingleFormValues = z.infer<typeof singleFormSchema>

export const SINGLE_DEFAULTS: SingleFormValues = {
  symbology: 'ean13',
  code: '',
  ...DEFAULT_OPTIONS,
}

/** Preview DPI: resolution doesn't change how the code looks, and it's faster. */
export const PREVIEW_DPI = 150
