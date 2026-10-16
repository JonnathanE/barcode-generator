const BYTES_PER_MB = 1024 * 1024

/** Client-side checks before uploading (RNF-03); the backend checks the content again. */
export function checkExcelFile(file: File, maxMb: number): string | null {
  if (!file.name.toLowerCase().endsWith('.xlsx')) {
    return file.name.toLowerCase().endsWith('.xls')
      ? 'El formato .xls antiguo no está soportado. Guárdalo como .xlsx.'
      : 'Sube un archivo de Excel (.xlsx).'
  }
  if (file.size > maxMb * BYTES_PER_MB) {
    return `El archivo supera el límite de ${String(maxMb)} MB.`
  }
  if (file.size === 0) return 'El archivo está vacío.'
  return null
}

export function formatSize(bytes: number): string {
  return bytes < BYTES_PER_MB
    ? `${String(Math.max(1, Math.round(bytes / 1024)))} KB`
    : `${(bytes / BYTES_PER_MB).toFixed(1)} MB`
}
