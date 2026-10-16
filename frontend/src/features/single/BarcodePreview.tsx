import { ImageIcon } from 'lucide-react'

import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

interface BarcodePreviewProps {
  imageUrl: string | null
  alt: string
  isWaiting: boolean
  transparent: boolean
  /** Why there is no image: invalid input, server not ready, request error. */
  message: string | null
}

// Always light, whatever the UI theme: a transparent code is meant to be printed on a
// light surface, and black bars on a dark checkerboard would be unreadable.
const CHECKERBOARD =
  'bg-white bg-[repeating-conic-gradient(#e5e5e5_0_25%,transparent_0_50%)] bg-size-[16px_16px]'

export function BarcodePreview({
  imageUrl,
  alt,
  isWaiting,
  transparent,
  message,
}: BarcodePreviewProps) {
  return (
    <div
      aria-busy={isWaiting}
      className="relative flex min-h-48 items-center justify-center rounded-lg border p-4"
    >
      {imageUrl && !message ? (
        <img
          src={imageUrl}
          alt={alt}
          className={cn(
            'max-h-80 max-w-full object-contain transition-opacity',
            transparent && CHECKERBOARD,
            isWaiting && 'opacity-60',
          )}
        />
      ) : isWaiting && !message ? (
        <Skeleton className="h-32 w-full max-w-sm" />
      ) : (
        <p className="text-muted-foreground flex flex-col items-center gap-2 text-center text-sm">
          <ImageIcon aria-hidden="true" className="size-8 opacity-50" />
          {message ?? 'Escribe un código para ver la vista previa.'}
        </p>
      )}
    </div>
  )
}
