// Apply the saved theme before first paint to avoid a light flash (same key as ThemeProvider).
try {
  const theme = localStorage.getItem('theme') ?? 'system'
  const dark =
    theme === 'dark' || (theme === 'system' && matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.classList.toggle('dark', dark)
} catch {}
