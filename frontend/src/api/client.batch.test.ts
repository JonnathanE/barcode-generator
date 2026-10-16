// @vitest-environment node
// The HTTP client doesn't touch the DOM. In Node, File, FormData and fetch share one
// implementation, like in a browser (jsdom's File is not accepted by Node's FormData).
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  API_URL,
  downloadTemplate,
  generateBatch,
  getBatchLimits,
  TIMEOUT_MS,
  validateBatch,
} from '@/api/client'

function stubFetch(response: Response) {
  const fetchMock = vi.fn<(request: Request) => Promise<Response>>(() => Promise.resolve(response))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const xlsx = new File(['excel-bytes'], 'codigos.xlsx', {
  type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
})
const options = {
  include_text: true,
  scale: 1,
  bar_height_mm: 22.85,
  dpi: 300 as const,
  bar_color: '#000000',
  background: '#FFFFFF',
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('batch client', () => {
  it('validateBatch sends the file and the flag as multipart', async () => {
    const fetchMock = stubFetch(
      Response.json({ summary: { total: 0, valid: 0, errors: 0, duplicates: 0 }, rows: [] }),
    )

    await validateBatch('ean13', { file: xlsx, restoreLeadingZeros: true })

    const request = fetchMock.mock.calls[0]?.[0]
    expect(request?.url).toBe(`${API_URL}/api/v1/batch/ean13/validate`)
    expect(request?.headers.get('Content-Type')).toMatch(/^multipart\/form-data; boundary=/)
    // The raw multipart body is what travels over the network.
    const body = (await request?.text()) ?? ''
    expect(body).toMatch(/name="file"; filename="codigos.xlsx"\r\n/)
    expect(body).toContain('excel-bytes')
    expect(body).toMatch(/name="restore_leading_zeros"\r\n\r\ntrue\r\n/)
  })

  it('generateBatch repeats formats, sends JSON options and returns the ZIP name', async () => {
    const fetchMock = stubFetch(
      new Response('zip-bytes', {
        headers: {
          'Content-Type': 'application/zip',
          'Content-Disposition': 'attachment; filename="codigos_20261016-120000.zip"',
        },
      }),
    )

    const result = await generateBatch('ean13', {
      file: xlsx,
      restoreLeadingZeros: false,
      formats: ['png', 'eps'],
      options,
    })

    expect(result.filename).toBe('codigos_20261016-120000.zip')
    const form = await fetchMock.mock.calls[0]?.[0].formData()
    expect(form?.getAll('formats')).toEqual(['png', 'eps'])
    expect(JSON.parse(String(form?.get('options')))).toEqual(options)
  })

  it('uses the long batch timeout for uploads', async () => {
    const timeoutSpy = vi.spyOn(AbortSignal, 'timeout')
    stubFetch(
      Response.json({ summary: { total: 0, valid: 0, errors: 0, duplicates: 0 }, rows: [] }),
    )

    await validateBatch('ean13', { file: xlsx, restoreLeadingZeros: false })

    expect(timeoutSpy).toHaveBeenCalledWith(TIMEOUT_MS.batch)
  })

  it('getBatchLimits posts formats and options as JSON', async () => {
    const fetchMock = stubFetch(
      Response.json({ max_rows: 241, max_upload_mb: 2, png_width_px: 4446, png_height_px: 930 }),
    )

    const limits = await getBatchLimits('ean13', { formats: ['png'], options })

    expect(limits.max_rows).toBe(241)
    expect(await fetchMock.mock.calls[0]?.[0].json()).toEqual({ formats: ['png'], options })
  })

  it('downloadTemplate returns the xlsx with its name', async () => {
    stubFetch(
      new Response('xlsx', {
        headers: { 'Content-Disposition': 'attachment; filename="plantilla_codigos.xlsx"' },
      }),
    )

    expect((await downloadTemplate()).filename).toBe('plantilla_codigos.xlsx')
  })
})
