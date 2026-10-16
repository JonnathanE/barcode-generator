import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  ApiError,
  type BatchRow,
  type BatchValidateResponse,
  generateBatch,
  getBatchLimits,
  getHealth,
  getSymbologies,
  validateBatch,
} from '@/api/client'
import { ServerStatusProvider } from '@/components/ServerStatusProvider'
import { BatchPage } from '@/features/batch/BatchPage'
import { saveBlob } from '@/lib/download'

vi.mock('@/api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/client')>()),
  getHealth: vi.fn<typeof getHealth>(),
  getSymbologies: vi.fn<typeof getSymbologies>(),
  getBatchLimits: vi.fn<typeof getBatchLimits>(),
  validateBatch: vi.fn<typeof validateBatch>(),
  generateBatch: vi.fn<typeof generateBatch>(),
}))
vi.mock('@/lib/download', () => ({ saveBlob: vi.fn<typeof saveBlob>() }))

const row = (overrides: Partial<BatchRow>): BatchRow => ({
  row: 2,
  input: '786123456789',
  normalized: '7861234567898',
  status: 'ok',
  message: '',
  filename: '7861234567898',
  ...overrides,
})

const REPORT: BatchValidateResponse = {
  summary: { total: 3, valid: 1, errors: 1, duplicates: 1 },
  rows: [
    row({ row: 2 }),
    row({
      row: 3,
      input: '7861234567897',
      normalized: null,
      status: 'error',
      message: 'El dígito de control debe ser 8.',
      filename: null,
    }),
    row({
      row: 4,
      status: 'duplicado',
      message: 'Repetido de la fila 2: se genera una sola vez.',
      filename: null,
    }),
  ],
}

const xlsx = () => new File(['excel'], 'codigos.xlsx')

function setup({ maxRows = 500 } = {}) {
  vi.mocked(getHealth).mockResolvedValue({ status: 'ok', version: '0.1.0' })
  vi.mocked(getSymbologies).mockResolvedValue([
    { id: 'ean13', name: 'EAN-13', formats: ['eps', 'png'] },
  ])
  vi.mocked(getBatchLimits).mockResolvedValue({
    max_rows: maxRows,
    max_upload_mb: 2,
    png_width_px: 4446,
    png_height_px: 930,
  })
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ServerStatusProvider>
        <BatchPage />
      </ServerStatusProvider>
    </QueryClientProvider>,
  )
  return userEvent.setup({ applyAccept: false })
}

async function uploadFile(user: ReturnType<typeof userEvent.setup>, file = xlsx()) {
  const input = await screen.findByLabelText(/Arrastra tu Excel/)
  await waitFor(() => {
    expect(input).toBeEnabled()
  })
  await user.upload(input, file)
}

beforeEach(() => {
  vi.mocked(validateBatch).mockReset().mockResolvedValue(REPORT)
  vi.mocked(generateBatch)
    .mockReset()
    .mockResolvedValue({ blob: new Blob(['zip']), filename: 'codigos_20261016.zip' })
})

describe('BatchPage', () => {
  it('validates on upload and shows the summary, table and fix instructions', async () => {
    const user = setup()

    await uploadFile(user)

    expect(await screen.findByText('1 fila tiene errores y no se generará')).toBeInTheDocument()
    expect(validateBatch).toHaveBeenCalledWith(
      'ean13',
      expect.objectContaining({ restoreLeadingZeros: false }),
    )
    const table = screen.getByRole('table')
    const errorRow = within(table).getByText('El dígito de control debe ser 8.').closest('tr')
    expect(errorRow).toHaveClass('bg-destructive/5')
    expect(within(errorRow as HTMLElement).getByText('Con error')).toBeInTheDocument()
  })

  it('on small screens each row is a card with its status and message', async () => {
    const user = setup()

    await uploadFile(user)

    const cards = within(await screen.findByRole('list', { name: 'Filas del archivo' }))
    const errorCard = cards.getByText('El dígito de control debe ser 8.').closest('li')
    expect(errorCard).toHaveClass('bg-destructive/5')
    expect(within(errorCard as HTMLElement).getByText('Fila 3')).toBeInTheDocument()
    expect(within(errorCard as HTMLElement).getByText('Con error')).toBeInTheDocument()
  })

  it('filters the table by status', async () => {
    const user = setup()
    await uploadFile(user)
    await screen.findByText('1 fila tiene errores y no se generará')

    await user.click(screen.getByRole('button', { name: 'Con error (1)' }))

    expect(screen.getByRole('button', { name: 'Con error (1)' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(
      screen.queryByText('Repetido de la fila 2: se genera una sola vez.'),
    ).not.toBeInTheDocument()
    expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(2) // header + 1
  })

  it('generates the ZIP with the chosen formats and options', async () => {
    const user = setup()
    await uploadFile(user)
    const button = await screen.findByRole('button', { name: 'Generar 1 código' })
    await waitFor(() => {
      expect(button).toBeEnabled()
    })

    await user.click(screen.getByLabelText('EPS vectorial')) // only PNG
    await user.click(button)

    await waitFor(() => {
      expect(saveBlob).toHaveBeenCalledWith(expect.any(Blob), 'codigos_20261016.zip')
    })
    expect(generateBatch).toHaveBeenCalledWith('ean13', {
      file: expect.any(File) as unknown,
      restoreLeadingZeros: false,
      formats: ['png'],
      options: expect.objectContaining({ scale: 1, dpi: 300, background: '#FFFFFF' }) as unknown,
    })
  })

  it('re-validates when restoring leading zeros', async () => {
    const user = setup()
    await uploadFile(user)
    await screen.findByText('1 fila tiene errores y no se generará')

    await user.click(screen.getByLabelText('Restaurar ceros iniciales'))

    await waitFor(() => {
      expect(validateBatch).toHaveBeenLastCalledWith(
        'ean13',
        expect.objectContaining({ restoreLeadingZeros: true }),
      )
    })
  })

  it('rejects non-xlsx files in the browser', async () => {
    const user = setup()

    await uploadFile(user, new File(['x'], 'codigos.csv'))

    expect(await screen.findByText('Sube un archivo de Excel (.xlsx).')).toBeInTheDocument()
    expect(validateBatch).not.toHaveBeenCalled()
  })

  it('explains a missing code column with the headers found', async () => {
    vi.mocked(validateBatch).mockRejectedValue(
      new ApiError('CODE_COLUMN_NOT_FOUND', 'No se encontró la columna de códigos.', 422, {
        headers_found: ['producto', 'precio'],
      }),
    )
    const user = setup()

    await uploadFile(user)

    expect(await screen.findByText('No se encontró la columna de códigos')).toBeInTheDocument()
    expect(screen.getByText(/«producto», «precio»/)).toBeInTheDocument()
  })

  it('shows the rate limit message from the API', async () => {
    vi.mocked(validateBatch).mockRejectedValue(
      new ApiError(
        'RATE_LIMITED',
        'Demasiadas solicitudes. Espera un momento e intenta de nuevo.',
        429,
      ),
    )
    const user = setup()

    await uploadFile(user)

    expect(await screen.findByText('Demasiadas solicitudes')).toBeInTheDocument()
  })

  it('disables Generate when there are no valid rows', async () => {
    vi.mocked(validateBatch).mockResolvedValue({
      summary: { total: 1, valid: 0, errors: 1, duplicates: 0 },
      rows: [REPORT.rows[1] as BatchRow],
    })
    const user = setup()

    await uploadFile(user)

    expect(await screen.findByText('No hay filas válidas para generar.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Generar' })).toBeDisabled()
  })

  it('disables Generate over the limit for large PNGs and says why', async () => {
    const user = setup({ maxRows: 0 })

    await uploadFile(user)

    expect(await screen.findByText(/el máximo es 0 códigos por lote/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Generar 1 código' })).toBeDisabled()
  })
})
