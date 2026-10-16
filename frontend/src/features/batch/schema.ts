import * as z from 'zod/mini'

import { barcodeOptionsSchema, DEFAULT_OPTIONS } from '@/lib/barcode-options'

export const batchFormSchema = z.extend(barcodeOptionsSchema, {
  symbology: z.string(),
  formats: z.array(z.enum(['png', 'eps'])).check(z.minLength(1, 'Elige al menos un formato.')),
  restore_leading_zeros: z.boolean(),
})

export type BatchFormValues = z.infer<typeof batchFormSchema>

export const BATCH_DEFAULTS: BatchFormValues = {
  symbology: 'ean13',
  formats: ['png', 'eps'],
  restore_leading_zeros: false,
  ...DEFAULT_OPTIONS,
}

/** Used until /limits answers. */
export const DEFAULT_MAX_UPLOAD_MB = 2
