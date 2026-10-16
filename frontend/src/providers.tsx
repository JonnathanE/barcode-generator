import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import { ServerStatusProvider } from '@/components/ServerStatusProvider'
import { ThemeProvider } from '@/components/ThemeProvider'
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'

const queryClient = new QueryClient({
  defaultOptions: {
    // Errors carry a user-facing message; retrying a 4xx would only repeat it.
    queries: { retry: false, refetchOnWindowFocus: false },
  },
})

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <TooltipProvider>
          <ServerStatusProvider>
            {children}
            <Toaster richColors closeButton />
          </ServerStatusProvider>
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}
