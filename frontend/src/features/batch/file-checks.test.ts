import { describe, expect, it } from 'vitest'

import { checkExcelFile, formatSize } from '@/features/batch/file-checks'

const file = (name: string, size: number) => new File([new Uint8Array(size)], name)

describe('checkExcelFile', () => {
  it.each([
    ['codigos.xlsx', 1000, null],
    ['CODIGOS.XLSX', 1000, null],
    ['codigos.xls', 1000, 'El formato .xls antiguo no está soportado. Guárdalo como .xlsx.'],
    ['codigos.csv', 1000, 'Sube un archivo de Excel (.xlsx).'],
    ['codigos.xlsm', 1000, 'Sube un archivo de Excel (.xlsx).'],
    ['vacio.xlsx', 0, 'El archivo está vacío.'],
    ['grande.xlsx', 2 * 1024 * 1024 + 1, 'El archivo supera el límite de 2 MB.'],
  ])('%s (%i bytes)', (name, size, expected) => {
    expect(checkExcelFile(file(name, size), 2)).toBe(expected)
  })
})

it('formatSize', () => {
  expect(formatSize(300)).toBe('1 KB')
  expect(formatSize(12_833)).toBe('13 KB')
  expect(formatSize(1.5 * 1024 * 1024)).toBe('1.5 MB')
})
