import { CircleAlertIcon } from 'lucide-react'

import { ApiError, type ApiErrorCode } from '@/api/client'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

const TITLES: Partial<Record<ApiErrorCode, string>> = {
  INVALID_FILE_TYPE: 'Archivo no válido',
  FILE_TOO_LARGE: 'El archivo es demasiado grande',
  TOO_MANY_ROWS: 'Demasiadas filas',
  CODE_COLUMN_NOT_FOUND: 'No se encontró la columna de códigos',
  RATE_LIMITED: 'Demasiadas solicitudes',
  TIMEOUT: 'El servidor tardó demasiado',
  NETWORK_ERROR: 'Sin conexión con el servidor',
}

function headersFound(error: ApiError): string[] {
  const found = error.details.headers_found
  return Array.isArray(found) ? found.map(String) : []
}

export function BatchErrorAlert({
  error,
  fallbackTitle,
}: {
  error: unknown
  fallbackTitle: string
}) {
  const apiError = error instanceof ApiError ? error : null
  const headers = apiError?.code === 'CODE_COLUMN_NOT_FOUND' ? headersFound(apiError) : []

  return (
    <Alert variant="destructive">
      <CircleAlertIcon aria-hidden="true" />
      <AlertTitle>{(apiError && TITLES[apiError.code]) ?? fallbackTitle}</AlertTitle>
      <AlertDescription>
        <p>{apiError?.message ?? 'Ocurrió un error inesperado. Intenta de nuevo.'}</p>
        {headers.length > 0 && (
          <p>
            Encabezados encontrados: {headers.map((h) => `«${h}»`).join(', ')}. Descarga la
            plantilla para ver el formato esperado.
          </p>
        )}
      </AlertDescription>
    </Alert>
  )
}
