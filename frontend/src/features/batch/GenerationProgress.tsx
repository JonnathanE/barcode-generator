import { useEffect, useState } from 'react'

/** Indeterminate progress: the backend doesn't report partial progress. */
export function GenerationProgress({ count }: { count: number }) {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const timer = setInterval(() => {
      setSeconds((value) => value + 1)
    }, 1_000)
    return () => {
      clearInterval(timer)
    }
  }, [])

  return (
    <div className="flex flex-col gap-2">
      <div className="bg-muted h-1.5 overflow-hidden rounded-full" aria-hidden="true">
        <div className="bg-primary animate-indeterminate h-full w-1/3 rounded-full" />
      </div>
      <output aria-live="polite" className="text-muted-foreground text-sm">
        Generando {count} {count === 1 ? 'código' : 'códigos'}… ({seconds} s). No cierres esta
        página.
      </output>
    </div>
  )
}
