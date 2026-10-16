import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, getHealth } from '@/api/client'
import { ServerStatus } from '@/components/ServerStatus'
import { ServerStatusProvider } from '@/components/ServerStatusProvider'
import { useServerReady } from '@/components/server-status-context'

vi.mock('@/api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/client')>()),
  getHealth: vi.fn<typeof getHealth>(),
}))
const getHealthMock = vi.mocked(getHealth)

function ReadyProbe() {
  return <span>{useServerReady() ? 'habilitado' : 'deshabilitado'}</span>
}

function renderStatus(slowAfterMs = 2_000) {
  const queryClient = new QueryClient()
  render(
    <QueryClientProvider client={queryClient}>
      <ServerStatusProvider slowAfterMs={slowAfterMs} retry={false}>
        <ServerStatus />
        <ReadyProbe />
      </ServerStatusProvider>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  getHealthMock.mockReset()
})

describe('ServerStatus', () => {
  it('shows ready and enables generation once /health answers', async () => {
    getHealthMock.mockResolvedValue({ status: 'ok', version: '0.1.0' })

    renderStatus()

    expect(await screen.findByText('Servidor listo')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Servidor listo')
    expect(screen.getByText('habilitado')).toBeInTheDocument()
  })

  it('tells the user the server is waking up when /health is slow', async () => {
    getHealthMock.mockReturnValue(new Promise(() => undefined))

    renderStatus(10)

    expect(screen.getByText('Comprobando servidor…')).toBeInTheDocument()
    expect(
      await screen.findByText('Iniciando servidor (puede tardar hasta 1 minuto)…'),
    ).toBeInTheDocument()
    expect(screen.getByText('deshabilitado')).toBeInTheDocument()
  })

  it('shows unavailable with a retry button that recovers', async () => {
    getHealthMock.mockRejectedValueOnce(
      new ApiError('NETWORK_ERROR', 'No se pudo conectar con el servidor.'),
    )
    getHealthMock.mockResolvedValueOnce({ status: 'ok', version: '0.1.0' })

    renderStatus()

    expect(await screen.findByText('Servidor no disponible')).toBeInTheDocument()
    expect(screen.getByText('deshabilitado')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(await screen.findByText('Servidor listo')).toBeInTheDocument()
    expect(getHealthMock).toHaveBeenCalledTimes(2)
  })
})
