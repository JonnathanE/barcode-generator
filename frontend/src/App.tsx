import { lazy, Suspense } from 'react'

import { GS1Notice } from '@/components/GS1Notice'
import { ServerStatus } from '@/components/ServerStatus'
import { ThemeToggle } from '@/components/ThemeToggle'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { SingleBarcodeForm } from '@/features/single/SingleBarcodeForm'

// Loaded on demand: people generating one code don't download the batch UI.
const BatchPage = lazy(() =>
  import('@/features/batch/BatchPage').then((module) => ({ default: module.BatchPage })),
)

function App() {
  return (
    <div className="flex min-h-svh flex-col">
      <header className="border-b">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div>
            <h1 className="text-lg font-semibold">Generador de Códigos de Barras</h1>
            <ServerStatus />
          </div>
          <ThemeToggle />
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-4 py-6">
        <Tabs defaultValue="single" className="gap-6">
          <TabsList aria-label="Modo de generación">
            <TabsTrigger value="single">Un código</TabsTrigger>
            <TabsTrigger value="batch">Masivo desde Excel</TabsTrigger>
          </TabsList>
          <TabsContent value="single">
            <SingleBarcodeForm />
          </TabsContent>
          <TabsContent value="batch">
            <Suspense fallback={<Skeleton className="h-96 w-full" />}>
              <BatchPage />
            </Suspense>
          </TabsContent>
        </Tabs>
        <GS1Notice />
      </main>

      <footer className="text-muted-foreground border-t px-4 py-4 text-center text-xs">
        Generado con{' '}
        <a
          href="https://bwipp.terryburton.co.uk/"
          target="_blank"
          rel="noreferrer"
          className="underline underline-offset-4"
        >
          BWIPP
        </a>{' '}
        · PNG y EPS vectorial listos para imprenta
      </footer>
    </div>
  )
}

export default App
