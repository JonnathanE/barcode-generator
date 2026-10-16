import type { Symbology } from '@/api/client'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

interface SymbologySelectProps {
  id: string
  value: string
  onChange: (value: string) => void
  symbologies: Symbology[]
}

/** RF-23: only EAN-13 today; new backend symbologies appear automatically. */
export function SymbologySelect({ id, value, onChange, symbologies }: SymbologySelectProps) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger id={id} className="w-full">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {symbologies.map((symbology) => (
          <SelectItem key={symbology.id} value={symbology.id}>
            {symbology.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
