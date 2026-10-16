import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  API_URL,
  ApiError,
  filenameFrom,
  getHealth,
  renderBarcode,
  toApiError,
  validateCode,
  withTimeout,
} from '@/api/client'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function mockFetch(response: Response | Error | DOMException) {
  // Not `instanceof Error`: in jsdom DOMException doesn't extend Error.
  const fetchMock = vi.fn<(request: Request) => Promise<Response>>(() =>
    response instanceof Response ? Promise.resolve(response) : Promise.reject(response),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('validateCode', () => {
  it('posts the code and returns the normalized result', async () => {
    const fetchMock = mockFetch(
      jsonResponse({ valid: true, normalized: '7861234567898', check_digit: 8 }),
    )

    const result = await validateCode('ean13', '786123456789')

    expect(result.normalized).toBe('7861234567898')
    const request = fetchMock.mock.calls[0]?.[0]
    expect(request?.url).toBe(`${API_URL}/api/v1/barcodes/ean13/validate`)
    expect(request?.method).toBe('POST')
    expect(await request?.json()).toEqual({ code: '786123456789' })
  })

  it('turns the backend error format into an ApiError', async () => {
    mockFetch(
      jsonResponse(
        {
          error: {
            code: 'INVALID_CHECK_DIGIT',
            message: 'El dígito de control debe ser 8.',
            details: { expected: 8, received: 7 },
          },
        },
        422,
      ),
    )

    const error = await validateCode('ean13', '7861234567897').catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      code: 'INVALID_CHECK_DIGIT',
      message: 'El dígito de control debe ser 8.',
      status: 422,
      details: { expected: 8, received: 7 },
    })
  })
})

describe('renderBarcode', () => {
  it('returns the blob and the filename from Content-Disposition', async () => {
    const fetchMock = mockFetch(
      new Response('png-bytes', {
        headers: {
          'Content-Type': 'image/png',
          'Content-Disposition': 'inline; filename="7861234567898.png"',
        },
      }),
    )

    const file = await renderBarcode(
      'ean13',
      { code: '786123456789', format: 'png' },
      { inline: true },
    )

    expect(file.filename).toBe('7861234567898.png')
    expect(await file.blob.text()).toBe('png-bytes')
    expect(fetchMock.mock.calls[0]?.[0].url).toBe(
      `${API_URL}/api/v1/barcodes/ean13/render?inline=true`,
    )
  })

  it('parses JSON errors even when expecting a blob', async () => {
    mockFetch(
      jsonResponse(
        { error: { code: 'RATE_LIMITED', message: 'Demasiadas solicitudes.', details: {} } },
        429,
      ),
    )

    await expect(renderBarcode('ean13', { code: '1', format: 'png' })).rejects.toMatchObject({
      code: 'RATE_LIMITED',
      status: 429,
    })
  })
})

describe('network failures', () => {
  it('maps a failed connection to NETWORK_ERROR', async () => {
    mockFetch(new TypeError('Failed to fetch'))

    await expect(getHealth()).rejects.toMatchObject({
      code: 'NETWORK_ERROR',
      message: 'No se pudo conectar con el servidor.',
    })
  })

  it('maps a timeout to TIMEOUT', async () => {
    mockFetch(new DOMException('signal timed out', 'TimeoutError'))

    await expect(getHealth()).rejects.toMatchObject({ code: 'TIMEOUT' })
  })

  it('lets caller cancellations propagate as AbortError', async () => {
    mockFetch(new DOMException('aborted', 'AbortError'))

    await expect(getHealth()).rejects.toMatchObject({ name: 'AbortError' })
  })
})

describe('helpers', () => {
  it('toApiError falls back to UNKNOWN for unexpected bodies', () => {
    expect(toApiError(502, '<html>Bad gateway</html>')).toMatchObject({
      code: 'UNKNOWN',
      status: 502,
    })
  })

  it('filenameFrom uses the fallback without the header', () => {
    expect(filenameFrom(new Headers(), 'codigo.eps')).toBe('codigo.eps')
  })

  it('withTimeout aborts when the caller aborts', () => {
    const controller = new AbortController()
    const signal = withTimeout(60_000, controller.signal)

    controller.abort()

    expect(signal.aborted).toBe(true)
  })
})
