import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { useDebouncedValue } from '@/hooks/use-debounced-value'

beforeEach(() => {
  vi.useFakeTimers()
})
afterEach(() => {
  vi.useRealTimers()
})

it('updates only after the delay without new changes', () => {
  const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 300), {
    initialProps: { value: 'a' },
  })

  rerender({ value: 'ab' })
  act(() => {
    vi.advanceTimersByTime(200)
  })
  rerender({ value: 'abc' })
  act(() => {
    vi.advanceTimersByTime(200)
  })
  expect(result.current).toBe('a')

  act(() => {
    vi.advanceTimersByTime(100)
  })
  expect(result.current).toBe('abc')
})
