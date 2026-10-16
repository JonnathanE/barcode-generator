import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getHealth, getSymbologies, renderBarcode } from '@/api/client'
import { ServerStatusProvider } from '@/components/ServerStatusProvider'
import { SingleBarcodeForm } from '@/features/single/SingleBarcodeForm'
import { saveBlob } from '@/lib/download'

vi.mock('@/api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/client')>()),
  getHealth: vi.fn<typeof getHealth>(),
  getSymbologies: vi.fn<typeof getSymbologies>(),
  renderBarcode: vi.fn<typeof renderBarcode>(),
}))
vi.mock('@/lib/download', () => ({ saveBlob: vi.fn<typeof saveBlob>() }))

const renderMock = vi.mocked(renderBarcode)
const pngBlob = new Blob(['png'], { type: 'image/png' })

function setup({ serverReady = true } = {}) {
  vi.mocked(getHealth).mockImplementation(() =>
    serverReady
      ? Promise.resolve({ status: 'ok', version: '0.1.0' })
      : new Promise(() => undefined),
  )
  vi.mocked(getSymbologies).mockResolvedValue([
    { id: 'ean13', name: 'EAN-13', formats: ['eps', 'png'] },
  ])
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ServerStatusProvider>
        <SingleBarcodeForm />
      </ServerStatusProvider>
    </QueryClientProvider>,
  )
  return { user: userEvent.setup(), code: screen.getByLabelText('Código') }
}

beforeEach(() => {
  vi.stubGlobal('URL', {
    ...URL,
    createObjectURL: () => 'blob:preview',
    revokeObjectURL: vi.fn<(url: string) => void>(),
  })
  renderMock.mockReset()
  renderMock.mockResolvedValue({ blob: pngBlob, filename: '7861234567898.png' })
})

describe('SingleBarcodeForm', () => {
  it('shows the expected check digit instantly and never calls the API', async () => {
    const { user, code } = setup()

    await user.type(code, '7861234567897')

    expect(await screen.findByText('El dígito de control debe ser 8.')).toBeInTheDocument()
    expect(code).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('button', { name: /Descargar PNG/ })).toBeDisabled()
    expect(renderMock).not.toHaveBeenCalled()
  })

  it('completes 12 digits and renders a debounced preview at 150 DPI', async () => {
    const { user, code } = setup()

    await user.type(code, '786-1234-56789')

    expect(screen.getByText('Código completo: 7861234567898')).toBeInTheDocument()
    expect(await screen.findByAltText('Código de barras 7861234567898')).toHaveAttribute(
      'src',
      'blob:preview',
    )
    expect(renderMock).toHaveBeenCalledTimes(1) // one request after typing stops
    expect(renderMock).toHaveBeenCalledWith(
      'ean13',
      {
        code: '786-1234-56789',
        format: 'png',
        options: {
          include_text: true,
          scale: 2,
          bar_height_mm: 22.85,
          dpi: 150,
          bar_color: '#000000',
          background: '#FFFFFF',
        },
      },
      expect.objectContaining({ inline: true }),
    )
  })

  it('downloads the EPS with the chosen options and the server filename', async () => {
    const { user, code } = setup()
    renderMock.mockResolvedValue({ blob: pngBlob, filename: '7861234567898.eps' })

    await user.type(code, '786123456789')
    const button = screen.getByRole('button', { name: /Descargar EPS/ })
    await waitFor(() => {
      expect(button).toBeEnabled()
    })
    await user.click(button)

    await waitFor(() => {
      expect(saveBlob).toHaveBeenCalledWith(pngBlob, '7861234567898.eps')
    })
    expect(renderMock).toHaveBeenCalledWith('ean13', {
      code: '786123456789',
      format: 'eps',
      options: expect.objectContaining({ dpi: 300 }) as unknown,
    })
  })

  it('keeps downloads disabled until the server is ready', async () => {
    const { user, code } = setup({ serverReady: false })

    await user.type(code, '786123456789')

    expect(screen.getByRole('button', { name: /Descargar PNG/ })).toBeDisabled()
    expect(screen.getByText('Esperando al servidor…')).toBeInTheDocument()
    expect(renderMock).not.toHaveBeenCalled()
  })
})
