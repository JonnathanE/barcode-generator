import createClient from 'openapi-fetch'

import type { components, paths } from '@/api/schema'

export type RenderRequest = components['schemas']['RenderRequest']
export type RenderOptions = components['schemas']['RenderOptionsIn']
export type OutputFormat = components['schemas']['OutputFormat']
export type Symbology = components['schemas']['SymbologyOut']
export type ValidateResponse = components['schemas']['ValidateResponse']
export type BatchValidateResponse = components['schemas']['BatchValidateResponse']
export type BatchRow = components['schemas']['BatchRowOut']
export type BatchRowStatus = components['schemas']['RowStatus']
export type BatchLimits = components['schemas']['BatchLimitsResponse']

export const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')

/** RNF-06: long enough to cover a Render cold start. */
export const TIMEOUT_MS = { single: 90_000, batch: 180_000 } as const

type ServerErrorCode = components['schemas']['ErrorCode']
export type ApiErrorCode = ServerErrorCode | 'NETWORK_ERROR' | 'TIMEOUT' | 'UNKNOWN'

export class ApiError extends Error {
  readonly code: ApiErrorCode
  readonly status: number | null
  readonly details: Record<string, unknown>

  constructor(
    code: ApiErrorCode,
    message: string,
    status: number | null = null,
    details: Record<string, unknown> = {},
  ) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
  }
}

// Late-bound fetch so tests can stub globalThis.fetch after the client is created.
const client = createClient<paths>({
  baseUrl: API_URL,
  fetch: (request) => globalThis.fetch(request),
})

/** Combine the caller's cancellation (e.g. TanStack Query) with a timeout. */
export function withTimeout(ms: number, signal?: AbortSignal): AbortSignal {
  const timeout = AbortSignal.timeout(ms)
  return signal ? AbortSignal.any([signal, timeout]) : timeout
}

/** Build an ApiError from a `{ error: { code, message, details } }` body (or anything else). */
export function toApiError(status: number, body: unknown): ApiError {
  if (isErrorBody(body)) {
    const { code, message, details } = body.error
    return new ApiError(code, message, status, details)
  }
  return new ApiError('UNKNOWN', `Error inesperado del servidor (${String(status)}).`, status)
}

function isErrorBody(body: unknown): body is components['schemas']['ErrorResponse'] {
  if (typeof body !== 'object' || body === null || !('error' in body)) return false
  const { error } = body
  return (
    typeof error === 'object' &&
    error !== null &&
    'code' in error &&
    typeof error.code === 'string' &&
    'message' in error &&
    typeof error.message === 'string'
  )
}

async function call<T>(request: () => Promise<{ data?: T; error?: unknown; response: Response }>) {
  let result: Awaited<ReturnType<typeof request>>
  try {
    result = await request()
  } catch (error) {
    // Compare by name: DOMException may come from another realm, so instanceof is unreliable.
    const name = error instanceof Error || error instanceof DOMException ? error.name : ''
    if (name === 'TimeoutError') {
      throw new ApiError('TIMEOUT', 'El servidor tardó demasiado en responder. Intenta de nuevo.')
    }
    // Caller cancellations (AbortError) propagate untouched so TanStack Query ignores them.
    if (name === 'AbortError') throw error
    throw new ApiError('NETWORK_ERROR', 'No se pudo conectar con el servidor.')
  }
  const { data, error, response } = result
  if (!response.ok || data === undefined) throw toApiError(response.status, error)
  return { data, response }
}

export async function getHealth(signal?: AbortSignal) {
  // One request covers a Render cold start (~25 s): Render holds it until the app is up.
  const { data } = await call(() =>
    client.GET('/health', { signal: withTimeout(TIMEOUT_MS.single, signal) }),
  )
  return data
}

export async function getSymbologies(signal?: AbortSignal): Promise<Symbology[]> {
  const { data } = await call(() =>
    client.GET('/api/v1/symbologies', { signal: withTimeout(TIMEOUT_MS.single, signal) }),
  )
  return data
}

export async function validateCode(
  symbology: string,
  code: string,
  signal?: AbortSignal,
): Promise<ValidateResponse> {
  const { data } = await call(() =>
    client.POST('/api/v1/barcodes/{symbology}/validate', {
      params: { path: { symbology } },
      body: { code },
      signal: withTimeout(TIMEOUT_MS.single, signal),
    }),
  )
  return data
}

export interface RenderedFile {
  blob: Blob
  filename: string
}

export async function renderBarcode(
  symbology: string,
  body: RenderRequest,
  { inline = false, signal }: { inline?: boolean; signal?: AbortSignal } = {},
): Promise<RenderedFile> {
  const { data, response } = await call(() =>
    client.POST('/api/v1/barcodes/{symbology}/render', {
      params: { path: { symbology }, query: { inline } },
      body,
      parseAs: 'blob',
      signal: withTimeout(TIMEOUT_MS.single, signal),
    }),
  )
  const fallback = `codigo.${body.format}`
  return { blob: data, filename: filenameFrom(response.headers, fallback) }
}

export function filenameFrom(headers: Headers, fallback: string): string {
  const match = /filename="([^"]+)"/.exec(headers.get('Content-Disposition') ?? '')
  return match?.[1] ?? fallback
}

export async function downloadTemplate(signal?: AbortSignal): Promise<RenderedFile> {
  const { data, response } = await call(() =>
    client.GET('/api/v1/batch/template', {
      parseAs: 'blob',
      signal: withTimeout(TIMEOUT_MS.single, signal),
    }),
  )
  return { blob: data, filename: filenameFrom(response.headers, 'plantilla_codigos.xlsx') }
}

export async function getBatchLimits(
  symbology: string,
  body: { formats: OutputFormat[]; options: RenderOptions },
  signal?: AbortSignal,
): Promise<BatchLimits> {
  const { data } = await call(() =>
    client.POST('/api/v1/batch/{symbology}/limits', {
      params: { path: { symbology } },
      body,
      signal: withTimeout(TIMEOUT_MS.single, signal),
    }),
  )
  return data
}

export interface BatchUpload {
  file: File
  restoreLeadingZeros: boolean
}

/**
 * openapi-typescript types binary form fields as `string`; at runtime FormData
 * takes the File itself. The cast is confined to this helper.
 */
function binary(file: Blob): string {
  return file as unknown as string
}

function toFormData(fields: Record<string, string | Blob | (string | Blob)[]>): FormData {
  const form = new FormData()
  for (const [name, value] of Object.entries(fields)) {
    for (const item of Array.isArray(value) ? value : [value]) form.append(name, item)
  }
  return form
}

/** Step 1: per-row report without rendering (RF-12). */
export async function validateBatch(
  symbology: string,
  { file, restoreLeadingZeros }: BatchUpload,
  signal?: AbortSignal,
): Promise<BatchValidateResponse> {
  const { data } = await call(() =>
    client.POST('/api/v1/batch/{symbology}/validate', {
      params: { path: { symbology } },
      body: { file: binary(file), restore_leading_zeros: restoreLeadingZeros },
      bodySerializer: () =>
        toFormData({ file, restore_leading_zeros: String(restoreLeadingZeros) }),
      signal: withTimeout(TIMEOUT_MS.batch, signal),
    }),
  )
  return data
}

/** Step 2: ZIP with the valid rows (RF-14). */
export async function generateBatch(
  symbology: string,
  {
    file,
    restoreLeadingZeros,
    formats,
    options,
  }: BatchUpload & { formats: OutputFormat[]; options: RenderOptions },
  signal?: AbortSignal,
): Promise<RenderedFile> {
  const { data, response } = await call(() =>
    client.POST('/api/v1/batch/{symbology}/generate', {
      params: { path: { symbology } },
      body: {
        file: binary(file),
        formats,
        options: JSON.stringify(options),
        restore_leading_zeros: restoreLeadingZeros,
      },
      bodySerializer: () =>
        toFormData({
          file,
          formats,
          options: JSON.stringify(options),
          restore_leading_zeros: String(restoreLeadingZeros),
        }),
      parseAs: 'blob',
      signal: withTimeout(TIMEOUT_MS.batch, signal),
    }),
  )
  return { blob: data, filename: filenameFrom(response.headers, 'codigos.zip') }
}
