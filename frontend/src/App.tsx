import { GS1Notice } from '@/components/GS1Notice'
import { ServerStatus } from '@/components/ServerStatus'
import { ThemeToggle } from '@/components/ThemeToggle'
import { SingleBarcodeForm } from '@/features/single/SingleBarcodeForm'

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
        <SingleBarcodeForm />
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
