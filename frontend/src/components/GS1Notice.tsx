import { InfoIcon } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

/** RF-21: a generated image doesn't grant the right to use the number. */
export function GS1Notice() {
  return (
    // role="note": a permanent notice, not an alert that interrupts screen readers.
    <Alert role="note">
      <InfoIcon aria-hidden="true" />
      <AlertTitle>Los códigos EAN-13 deben estar asignados por GS1</AlertTitle>
      <AlertDescription>
        Generar la imagen no otorga el derecho de usar el número en el comercio. Para vender un
        producto necesitas códigos asignados a tu empresa por GS1 (en Ecuador,{' '}
        <a
          href="https://www.gs1ec.org/"
          target="_blank"
          rel="noreferrer"
          className="text-foreground underline underline-offset-4"
        >
          GS1 Ecuador
        </a>
        ).
      </AlertDescription>
    </Alert>
  )
}
