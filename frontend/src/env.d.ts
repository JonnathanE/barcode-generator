interface ImportMetaEnv {
  /** Base URL of the backend, e.g. https://barcode-generator-api.onrender.com */
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
