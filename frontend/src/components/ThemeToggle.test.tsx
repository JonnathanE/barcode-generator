import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'

import { ThemeProvider } from '@/components/ThemeProvider'
import { ThemeToggle } from '@/components/ThemeToggle'

beforeEach(() => {
  localStorage.clear()
  document.documentElement.className = ''
  vi.stubGlobal('matchMedia', () => ({
    matches: false,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }))
})

it('applies and remembers the chosen theme', async () => {
  render(
    <ThemeProvider>
      <ThemeToggle />
    </ThemeProvider>,
  )
  const dark = screen.getByRole('button', { name: 'Tema oscuro' })
  expect(screen.getByRole('button', { name: 'Tema del sistema' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )

  await userEvent.click(dark)

  expect(document.documentElement).toHaveClass('dark')
  expect(dark).toHaveAttribute('aria-pressed', 'true')
  expect(localStorage.getItem('theme')).toBe('dark')
})
