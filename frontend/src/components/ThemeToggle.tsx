import { MonitorIcon, MoonIcon, SunIcon } from 'lucide-react'
import { useTheme } from 'next-themes'

import { Button } from '@/components/ui/button'

const OPTIONS = [
  { value: 'light', label: 'Tema claro', Icon: SunIcon },
  { value: 'dark', label: 'Tema oscuro', Icon: MoonIcon },
  { value: 'system', label: 'Tema del sistema', Icon: MonitorIcon },
] as const

export function ThemeToggle() {
  const { theme = 'system', setTheme } = useTheme()

  return (
    <fieldset className="bg-muted flex rounded-lg p-0.5">
      <legend className="sr-only">Tema</legend>
      {OPTIONS.map(({ value, label, Icon }) => (
        <Button
          key={value}
          type="button"
          variant={theme === value ? 'secondary' : 'ghost'}
          size="icon-sm"
          aria-label={label}
          aria-pressed={theme === value}
          title={label}
          onClick={() => {
            setTheme(value)
          }}
        >
          <Icon aria-hidden="true" />
        </Button>
      ))}
    </fieldset>
  )
}
