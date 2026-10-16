import { useEffect, useState } from 'react'

/**
 * Value that only updates after `delayMs` without changes. Use primitives
 * (e.g. a serialized request): a new object identity per render would keep
 * resetting the timer.
 */
export function useDebouncedValue<T extends string | number | boolean | null>(
  value: T,
  delayMs: number,
): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebounced(value)
    }, delayMs)
    return () => {
      clearTimeout(timer)
    }
  }, [value, delayMs])
  return debounced
}
