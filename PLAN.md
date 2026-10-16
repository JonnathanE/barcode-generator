# Plan de desarrollo — Generador de Códigos de Barras

> Documento maestro del proyecto. Claude Code debe implementarlo **fase por fase**, en orden, sin adelantar fases. Cada fase termina cuando se cumplen todos sus criterios de aceptación.

---

## 1. Contexto

Aplicación web para generar códigos de barras listos para imprenta, inspirada en el generador de Terry Burton (https://the-burtons.xyz/barcode-generator/), que usa el motor open source **BWIPP** (Barcode Writer in Pure PostScript).

- **MVP:** solo EAN-13, descarga en **PNG** y **EPS (vectorial)**.
- **Dos modos:** generación individual y generación masiva desde Excel.
- **Sin autenticación.**
- **Futuro:** más simbologías (QR, Code 128, EAN-8, UPC-A, ITF-14, DataMatrix…) y más formatos (SVG, PDF). La arquitectura debe permitir agregarlos sin reescribir endpoints ni UI.

### 1.1 Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, `treepoem` (BWIPP) + Ghostscript, `openpyxl` |
| Tooling backend | `uv` (dependencias), `ruff` (lint/format), `mypy`, `pytest` |
| Frontend | React + Vite + TypeScript, shadcn/ui, Tailwind, `react-hook-form` + `zod`, TanStack Query |
| Tooling frontend | `pnpm` (dependencias), `oxlint` (lint), Prettier (formato), `tsc` (tipos), Vitest (tests) |
| Tipos compartidos | `openapi-typescript` generado desde `/openapi.json` de FastAPI |
| Repositorio | Monorepo simple (`backend/`, `frontend/`), sin Nx/Turborepo |
| Despliegue | Frontend en **Vercel** (free) · Backend en **Render** (free, Docker) |
| CI | GitHub Actions con filtros por ruta |

### 1.2 Restricciones del plan gratuito (impactan el diseño)

| Restricción (Render free) | Consecuencia en el diseño |
|---|---|
| Se duerme tras 15 min sin tráfico; ~1 min en despertar | El front hace *warm-up* a `/health` al cargar y muestra estado "Iniciando servidor…" |
| 0.1 CPU | Límite de filas conservador y configurable; generación en threadpool; medir y ajustar |
| 512 MB RAM | Límite de tamaño de archivo; lectura de Excel en modo `read_only`; ZIP en memoria acotado |
| Disco efímero | **Nada se escribe en disco.** Todo en memoria (`io.BytesIO`). Flujo masivo *stateless* |
| Servicio público sin auth | CORS restringido al dominio de Vercel + rate limiting por IP |

---

## 2. Alcance

### 2.1 Dentro del MVP
- Generación individual EAN-13 con vista previa y descarga PNG/EPS.
- Generación masiva desde `.xlsx` con validación previa, reporte de errores y descarga ZIP.
- Plantilla Excel descargable.
- Despliegue en Vercel + Render con CI.

### 2.2 Fuera del MVP (no implementar todavía)
- Otras simbologías y formatos (solo dejar la arquitectura lista).
- Autenticación, historial, base de datos.
- Hojas de etiquetas en PDF.
- Procesamiento asíncrono con colas.

---

## 3. Requerimientos funcionales

### 3.1 Generación individual

| ID | Requerimiento |
|---|---|
| RF-01 | El usuario ingresa un código EAN-13 de **12 dígitos** (el sistema calcula el dígito de control) o **13 dígitos** (el sistema lo verifica). |
| RF-02 | Se rechazan entradas con caracteres no numéricos, longitud distinta de 12/13 o dígito de control incorrecto, con un mensaje claro que indique el dígito esperado. |
| RF-03 | Se ignoran espacios y guiones al inicio, final o intermedios (`786-1234-56789` → `786123456789`). |
| RF-04 | Vista previa PNG que se actualiza al escribir (debounce de 300 ms), solo cuando la entrada es válida. |
| RF-05 | Opciones configurables: mostrar texto legible (sí/no, por defecto sí), escala (1–5, por defecto 1 en la UI; la API mantiene 2 si no se envía), altura de barras en mm (10–50, por defecto 22.85 mm) y DPI para PNG (150, 300, 600; por defecto 300). La **escala es magnificación física**: ancho de módulo = 0,33 mm × escala (1 = 100 % GS1, 2 = 200 %) y aplica igual a PNG y EPS; la altura de barras es la altura final real; el DPI solo define la resolución del PNG (y se guarda como metadato `pHYs`). Escalas > 2 quedan fuera del rango GS1 (80 %–200 %) y la UI lo advierte. **Colores:** `bar_color` (barras y texto, hex `#RRGGBB`, por defecto `#000000`) y `background` (`#FFFFFF` por defecto, `transparent` o cualquier hex `#RRGGBB`); aplican a PNG y EPS. La UI advierte cuando el contraste es insuficiente para lectores (barras claras, rojas/naranjas/amarillas, o fondo oscuro). |
| RF-06 | Descarga en **PNG** y **EPS vectorial**. Nombre del archivo: `<codigo13>.png` / `<codigo13>.eps`. |
| RF-06a | Los archivos incluyen **siempre la zona de silencio** de EAN-13 (11 módulos a la izquierda, 7 a la derecha) dentro de su tamaño, pintada con el color de fondo (o transparente). Con texto legible se dibuja el indicador `>` de zona libre (opción `guardwhitespace` de BWIPP). |
| RF-07 | La validación del dígito de control también se ejecuta en el cliente para retroalimentación instantánea; el backend es la fuente de verdad. |

### 3.2 Generación masiva

| ID | Requerimiento |
|---|---|
| RF-08 | El usuario descarga una **plantilla `.xlsx`** con columnas `codigo` (formato Texto) y `nombre_archivo` (opcional), con filas de ejemplo. |
| RF-09 | El usuario sube un `.xlsx` (arrastrar y soltar o selector). Se lee la **primera hoja**. |
| RF-10 | La columna de códigos se detecta por encabezado, sin distinguir mayúsculas ni tildes: `codigo`, `código`, `ean`, `ean13`, `gtin`. La columna de nombre: `nombre_archivo`, `nombre`, `archivo`. |
| RF-11 | Se normalizan valores que Excel convierte en número: enteros (`7861234567890`), flotantes (`7861234567890.0`) y notación científica (`7.86123E+12`, marcada como **error** si se perdió precisión). Se restauran ceros iniciales solo si el valor tiene 11 o 12 dígitos y el usuario lo indicó con el flag opcional `restore_leading_zeros` (por defecto `false`; ver §5.4). Sin el flag, esas filas quedan como `error` con un mensaje que sugiere formatear la columna como Texto. |
| RF-12 | **Paso 1 – Validar:** el backend devuelve, sin generar imágenes, un reporte por fila: número de fila, valor original, código normalizado, estado (`ok`, `error`, `duplicado`) y mensaje. |
| RF-13 | El front muestra el reporte en una tabla con filtros (todos / válidos / con error) y resumen (total, válidos, errores, duplicados). |
| RF-14 | **Paso 2 – Generar:** el usuario elige formatos (PNG, EPS o ambos) y las mismas opciones de RF-05, y descarga un ZIP. Se generan solo las filas válidas. |
| RF-15 | Estructura del ZIP: `png/<nombre>.png`, `eps/<nombre>.eps`, `reporte.csv` (todas las filas con su estado). |
| RF-16 | Nombre de archivo: `nombre_archivo` si existe (sanitizado), si no el código de 13 dígitos. Colisiones se resuelven con sufijo `_2`, `_3`… |
| RF-17 | Códigos duplicados se generan una sola vez y se marcan como `duplicado` en el reporte. |
| RF-18 | Filas vacías se ignoran sin contarse como error. |
| RF-19 | Si el archivo supera el límite de filas o de tamaño, se rechaza completo con un mensaje que indica el límite. |

### 3.3 Generales

| ID | Requerimiento |
|---|---|
| RF-20 | Al cargar la app, el front llama a `/health` y muestra el estado del servidor: *Listo* / *Iniciando servidor (puede tardar hasta 1 minuto)…* / *No disponible*. |
| RF-21 | Aviso visible: generar la imagen no otorga el derecho de usar el número en el comercio; los EAN-13 deben estar asignados por GS1 (en Ecuador, GS1 Ecuador). |
| RF-22 | Interfaz en español. |
| RF-23 | La UI tiene un selector de simbología (por ahora solo "EAN-13"), preparado para agregar más. |

---

## 4. Requerimientos no funcionales

### 4.1 Rendimiento y recursos
| ID | Requerimiento |
|---|---|
| RNF-01 | Generación individual en < 2 s con el servidor despierto. |
| RNF-02 | Lote por defecto de hasta **500 filas** (`MAX_BATCH_ROWS`, configurable). Medir el tiempo real en Render en la Fase 5 y ajustar. |
| RNF-03 | Tamaño máximo de archivo **2 MB** (`MAX_UPLOAD_MB`), validado antes de parsear. |
| RNF-04 | La generación (subproceso de Ghostscript, bloqueante) se ejecuta en threadpool para no bloquear el event loop. |
| RNF-05 | Lectura de Excel con `openpyxl` en modo `read_only=True, data_only=True`. |
| RNF-06 | Timeouts del cliente: 90 s para individual (cubre el cold start), 180 s para masivo. |

### 4.2 Almacenamiento
| ID | Requerimiento |
|---|---|
| RNF-07 | **Prohibido escribir en disco** en tiempo de ejecución. Archivos, ZIP y CSV se construyen en memoria. |
| RNF-08 | El flujo masivo es *stateless*: el paso de generar vuelve a recibir el archivo (no se guarda nada entre validar y generar). |

### 4.3 Seguridad
| ID | Requerimiento |
|---|---|
| RNF-09 | CORS permitido solo para los orígenes en `ALLOWED_ORIGINS` (dominio de Vercel y `localhost` en desarrollo). Nunca `*` en producción. |
| RNF-10 | Rate limiting por IP con `slowapi`: individual `60/minute`, masivo `5/minute` (configurables). |
| RNF-11 | Validación del archivo por contenido (firma ZIP de `.xlsx`), no solo por extensión. Se rechazan `.xlsm` y archivos con macros. |
| RNF-12 | Sanitización de nombres de archivo (sin `/`, `\`, `..`, caracteres de control; máximo 100 caracteres) para evitar *path traversal* dentro del ZIP. |
| RNF-13 | Los datos de los usuarios no se registran en logs (solo conteos y tiempos). |
| RNF-14 | Las respuestas de error no exponen trazas internas. |

### 4.4 Calidad y mantenibilidad
| ID | Requerimiento |
|---|---|
| RNF-15 | Cobertura ≥ 90 % en el dominio (validación EAN-13 y normalización de Excel); ≥ 75 % global del backend. |
| RNF-16 | **Prueba de escaneo:** los tests decodifican los PNG generados con `zxing-cpp` y comparan con el código esperado. |
| RNF-17 | **Prueba de EPS vectorial:** el EPS debe tener cabecera `%!PS-Adobe-3.0 EPSF-3.0`, `%%BoundingBox` y no contener imágenes raster embebidas. |
| RNF-18 | Backend: `ruff` + `mypy --strict` sin errores. Frontend: `oxlint` + `tsc --noEmit` sin errores, Prettier. Gestor de paquetes: `pnpm` (versión fijada en `packageManager`). |
| RNF-19 | Extensibilidad: agregar una simbología nueva requiere solo registrar una clase en el `SymbologyRegistry` y su entrada en el selector del front. |
| RNF-20 | Configuración por variables de entorno (`pydantic-settings`), sin valores sensibles en el repo. |

### 4.5 Usabilidad y accesibilidad
| ID | Requerimiento |
|---|---|
| RNF-21 | Diseño responsive (funciona desde 360 px de ancho). |
| RNF-22 | Accesibilidad: componentes shadcn (Radix), labels en todos los inputs, errores anunciados con `aria-live`, navegación completa por teclado. |
| RNF-23 | Tema claro/oscuro. |

### 4.6 Operación
| ID | Requerimiento |
|---|---|
| RNF-24 | Logs estructurados en JSON (nivel, endpoint, duración, conteos). |
| RNF-25 | Endpoint `/health` liviano, usado por Render (`healthCheckPath`) y por el warm-up del front. |
| RNF-26 | Deploy automático: push a `main` → Vercel (si cambia `frontend/`) y Render (si cambia `backend/`). |

---

## 5. Arquitectura

### 5.1 Estructura del monorepo

```
barcode-generator/
├── backend/
│   ├── app/
│   │   ├── main.py                    # app FastAPI, CORS, rate limit, routers, handlers de error
│   │   ├── core/
│   │   │   ├── config.py              # Settings (pydantic-settings)
│   │   │   ├── errors.py              # AppError + códigos de error
│   │   │   └── logging.py             # logs JSON
│   │   ├── domain/
│   │   │   ├── ean13.py               # normalizar, calcular y validar dígito de control
│   │   │   └── filenames.py           # sanitización y resolución de colisiones
│   │   ├── symbologies/
│   │   │   ├── base.py                # Protocol Symbology + OutputFormat (enum)
│   │   │   ├── registry.py            # SymbologyRegistry
│   │   │   └── ean13.py               # implementación EAN-13
│   │   ├── services/
│   │   │   ├── renderer.py            # BWIPP/treepoem/Ghostscript → PNG y EPS
│   │   │   ├── excel_reader.py        # lectura y normalización de filas
│   │   │   ├── template.py            # plantilla .xlsx
│   │   │   └── batch.py               # validar lote, armar ZIP y reporte.csv
│   │   ├── api/routes/
│   │   │   ├── health.py
│   │   │   ├── barcodes.py
│   │   │   └── batch.py
│   │   └── schemas/                   # modelos Pydantic de request/response
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── fixtures/                  # .xlsx de prueba
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/ui/             # shadcn
│   │   ├── components/                # ServerStatus, GS1Notice, SymbologySelect, BarcodeOptions
│   │   ├── features/single/           # generación individual
│   │   ├── features/batch/            # carga, tabla de validación, descarga ZIP
│   │   ├── lib/ean13.ts               # validación en cliente (espejo del dominio)
│   │   ├── api/
│   │   │   ├── client.ts              # fetch con timeout y manejo de errores
│   │   │   └── schema.d.ts            # generado por openapi-typescript
│   │   └── App.tsx
│   ├── .env.example
│   └── package.json
├── .github/workflows/
│   ├── backend.yml
│   └── frontend.yml
├── docker-compose.yml                 # desarrollo local
├── render.yaml                        # blueprint de Render
├── CLAUDE.md
├── PLAN.md
└── README.md
```

**Convención de nombres:** código (variables, funciones, clases, endpoints) en **inglés**; textos de la UI, mensajes de error al usuario y documentación en **español**.

### 5.2 Diseño extensible de simbologías

```python
class OutputFormat(StrEnum):
    PNG = "png"
    EPS = "eps"

class Symbology(Protocol):
    id: str                       # "ean13"
    bwipp_name: str               # "ean13"
    supported_formats: set[OutputFormat]
    def normalize(self, raw: str) -> str: ...      # lanza AppError si es inválido
    def bwipp_options(self, opts: RenderOptions) -> dict[str, str]: ...
```

El `renderer` solo conoce `Symbology` y `OutputFormat`; los endpoints reciben `symbology` como parámetro de ruta y lo resuelven en el `SymbologyRegistry`.

### 5.3 Generación de EPS vectorial — decisión crítica

> ⚠️ **Trampa conocida:** `treepoem` devuelve una imagen de Pillow. Guardarla con `image.save("x.eps")` produce un EPS con un **bitmap embebido**, no un vector. Eso **no** cumple el requerimiento.

Estrategia (se valida en la Fase 1):

1. **Opción A (preferida):** usar BWIPP como PostScript (el `barcode.ps` que trae `treepoem`), construir el programa PostScript de invocación y convertirlo con Ghostscript: `gs -dNOPAUSE -dBATCH -dSAFER -sDEVICE=eps2write -sOutputFile=- -`. Resultado: EPS vectorial con `BoundingBox` ajustado.
2. **Opción B (fallback):** escribir un generador EPS propio para EAN-13 a partir del patrón de módulos (rectángulos + texto en OCR-B/Helvetica). Simple para EAN-13, pero habría que repetirlo por simbología.
3. El PNG sí puede salir de `treepoem` (raster), con DPI y escala configurables.

Toda llamada a Ghostscript usa `-dSAFER`, entrada por stdin, salida por stdout (sin archivos temporales) y timeout.

### 5.4 Contrato de la API (v1)

Base: `/api/v1`. Errores siempre con el formato:

```json
{ "error": { "code": "INVALID_CHECK_DIGIT", "message": "El dígito de control debe ser 8.", "details": {} } }
```

Códigos de error: `INVALID_CHARACTERS`, `INVALID_LENGTH`, `INVALID_CHECK_DIGIT`, `UNSUPPORTED_SYMBOLOGY`, `UNSUPPORTED_FORMAT`, `FILE_TOO_LARGE`, `TOO_MANY_ROWS`, `INVALID_FILE_TYPE`, `CODE_COLUMN_NOT_FOUND`, `RATE_LIMITED`, `RENDER_FAILED`, `INVALID_REQUEST` (validación del cuerpo o parámetros), `NOT_FOUND` (ruta inexistente), `INTERNAL_ERROR` (error inesperado, sin trazas).

| Método | Ruta | Entrada | Salida |
|---|---|---|---|
| GET | `/health` | — | `{"status":"ok","version":"x.y.z"}` |
| GET | `/api/v1/symbologies` | — | Lista de simbologías y formatos soportados |
| POST | `/api/v1/barcodes/{symbology}/validate` | `{ "code": "786123456789" }` | `{ "valid": true, "normalized": "7861234567898", "check_digit": 8 }` |
| POST | `/api/v1/barcodes/{symbology}/render` | `{ "code", "format": "png"\|"eps", "options": { include_text, scale, bar_height_mm, dpi, bar_color, background } }` | Archivo binario. `?inline=true` para la vista previa; si no, `Content-Disposition: attachment` |
| GET | `/api/v1/batch/template` | — | `plantilla_codigos.xlsx` |
| POST | `/api/v1/batch/{symbology}/validate` | multipart: `file`, `restore_leading_zeros` (bool, opcional, por defecto `false`) | `{ "summary": {total, valid, errors, duplicates}, "rows": [{row, input, normalized, status, message, filename}] }` |
| POST | `/api/v1/batch/{symbology}/generate` | multipart: `file`, `formats` (lista), `options` (JSON), `restore_leading_zeros` (bool, opcional) | `codigos_<fecha>.zip` |

### 5.5 Variables de entorno

**Backend (`backend/.env.example`)**
```
APP_ENV=development
ALLOWED_ORIGINS=http://localhost:5173
MAX_UPLOAD_MB=2
MAX_BATCH_ROWS=500
RATE_LIMIT_SINGLE=60/minute
RATE_LIMIT_BATCH=5/minute
GHOSTSCRIPT_TIMEOUT_SECONDS=20
LOG_LEVEL=INFO
```

**Frontend (`frontend/.env.example`)**
```
VITE_API_URL=http://localhost:8000
```

---

## 6. Fases de desarrollo

> Regla para cada fase: implementar → tests → lint/typecheck → verificar criterios de aceptación → commit con mensaje convencional (`feat:`, `fix:`, `chore:`, `test:`, `docs:`).

### Fase 0 — Esqueleto del monorepo
**Tareas**
1. Crear la estructura de carpetas de la sección 5.1, `README.md`, `.gitignore` (Python + Node), `.editorconfig`.
2. Backend: proyecto con `uv`, FastAPI, `ruff`, `mypy`, `pytest`; `main.py` con `/health`; `config.py` con `pydantic-settings`.
3. `Dockerfile` del backend: imagen `python:3.12-slim`, instalar `ghostscript` con apt, usuario no root, `uvicorn` escuchando en `$PORT` (Render lo inyecta).
4. Frontend: Vite + React + TS, Tailwind, inicializar shadcn, ESLint + Prettier, alias `@/`.
5. `docker-compose.yml` para levantar backend (con recarga) y frontend en local.

**Criterios de aceptación**
- `docker compose up` levanta ambos servicios; `GET localhost:8000/health` responde `ok`; el front abre en `localhost:5173`.
- `gs --version` funciona dentro del contenedor del backend.
- Lint y typecheck pasan en ambos proyectos.

### Fase 1 — Spike de generación (PNG + EPS vectorial)
**Objetivo:** eliminar el mayor riesgo técnico antes de construir lo demás.

**Tareas**
1. `services/renderer.py`: función que recibe código EAN-13 + opciones y devuelve bytes PNG (vía `treepoem`).
2. Implementar la **Opción A** de la sección 5.3 para EPS vectorial. Si no es viable, documentar por qué en el README e implementar la **Opción B**.
3. Script `backend/scripts/spike_render.py` que genere `7861234567898.png` y `.eps` en una carpeta local de pruebas (solo en el spike; nunca en la app).
4. Tests: decodificar el PNG con `zxing-cpp`; verificar cabecera EPSF, `BoundingBox` y ausencia de raster en el EPS.

**Criterios de aceptación**
- El PNG se decodifica correctamente con `zxing-cpp`.
- El EPS abre en Inkscape/Illustrator como vectores (al hacer zoom no se pixela).
- Ninguna llamada a Ghostscript usa archivos temporales; todas usan `-dSAFER` y timeout.
- Tiempo medido de una generación queda anotado en el README.

### Fase 2 — Dominio y API individual
**Tareas**
1. `domain/ean13.py`: limpiar entrada (RF-03), calcular dígito de control, validar (RF-01, RF-02). Tests con casos válidos, inválidos y bordes.
2. `symbologies/` con `Protocol`, `registry` e implementación EAN-13 (sección 5.2).
3. `core/errors.py` y handler global con el formato de error de la sección 5.4.
4. Endpoints: `/symbologies`, `/barcodes/{symbology}/validate`, `/barcodes/{symbology}/render` (generación en threadpool, RNF-04).
5. CORS (RNF-09) y rate limiting con `slowapi` (RNF-10).
6. Logs JSON (RNF-24) sin datos del usuario (RNF-13).

**Criterios de aceptación**
- Swagger (`/docs`) muestra todos los endpoints con ejemplos.
- Cobertura del dominio ≥ 90 %.
- Un código de 12 dígitos devuelve el de 13 correcto; un dígito de control erróneo devuelve `INVALID_CHECK_DIGIT` con el dígito esperado.
- Superar el rate limit devuelve 429 con `RATE_LIMITED`.

### Fase 3 — Primer despliegue del backend (Render)
**Tareas**
1. `render.yaml`: servicio `web`, `runtime: docker`, `rootDir: backend`, `plan: free`, `healthCheckPath: /health`, variables de entorno.
2. Workflow `.github/workflows/backend.yml`: en cambios a `backend/**` ejecuta `ruff`, `mypy`, `pytest`, y `docker build` de prueba.
3. Desplegar y probar `/health` y `/render` en la URL de Render.

**Criterios de aceptación**
- La URL pública de Render responde `/health` y genera PNG y EPS.
- Tiempo de cold start medido y anotado en el README.
- CI en verde.

### Fase 4 — Frontend: generación individual + despliegue en Vercel
**Tareas**
1. Generar tipos con `openapi-typescript` (script `pnpm gen:api` contra el backend local).
2. `api/client.ts`: fetch con `VITE_API_URL`, timeout (RNF-06) y parseo del formato de error.
3. `components/ServerStatus`: warm-up a `/health` al cargar con reintentos; estados de RF-20. Los botones de generar se deshabilitan hasta que el servidor esté listo.
4. `lib/ean13.ts`: validación en cliente (RF-07) con tests (Vitest).
5. `features/single`: formulario (`react-hook-form` + `zod`), selector de simbología (RF-23), opciones (RF-05), vista previa con debounce (RF-04), botones de descarga PNG/EPS (RF-06).
6. `GS1Notice` (RF-21), tema claro/oscuro (RNF-23), layout responsive (RNF-21).
7. Workflow `frontend.yml`: lint, typecheck, tests, build en cambios a `frontend/**`.
8. Vercel: Root Directory = `frontend`, variable `VITE_API_URL` = URL de Render. Agregar el dominio de Vercel a `ALLOWED_ORIGINS` en Render.

**Criterios de aceptación**
- Desde la URL de Vercel se genera y descarga un PNG y un EPS válidos.
- Con el backend dormido, la UI muestra "Iniciando servidor…" y se recupera sola al despertar.
- Navegable completamente con teclado; sin errores en consola.

### Fase 5 — Backend: generación masiva
**Tareas**
1. `services/template.py`: plantilla con columna `codigo` en formato Texto (`number_format = "@"`) y ejemplos (RF-08).
2. `services/excel_reader.py`: validación de tamaño (RNF-03) y firma del archivo (RNF-11) **antes** de parsear; lectura `read_only` (RNF-05); detección de columnas (RF-10); normalización de valores numéricos y notación científica (RF-11); filas vacías (RF-18); límite de filas (RF-19).
3. `domain/filenames.py`: sanitización (RNF-12) y colisiones (RF-16).
4. `services/batch.py`: validación del lote con duplicados (RF-12, RF-17); generación del ZIP en memoria con `png/`, `eps/`, `reporte.csv` (RF-15).
5. Endpoints `/batch/template`, `/batch/{symbology}/validate`, `/batch/{symbology}/generate` con rate limit de masivo.
6. Fixtures `.xlsx` de prueba: códigos válidos, inválidos, numéricos, notación científica, duplicados, filas vacías, nombres peligrosos (`../../x`), archivo sin columna `codigo`, archivo renombrado que no es xlsx.
7. **Medición en Render:** generar lotes de 50, 200 y 500 con ambos formatos; anotar tiempos y memoria en el README; ajustar `MAX_BATCH_ROWS` si es necesario.

**Criterios de aceptación**
- Todos los fixtures producen el resultado esperado (tests de integración).
- El ZIP contiene la estructura correcta y cada PNG del ZIP se decodifica con `zxing-cpp`.
- No se escribe ningún archivo en disco (verificado con un test que monitorea el directorio temporal o revisión de código).
- Un lote del tamaño máximo termina dentro del timeout del cliente en Render.

### Fase 6 — Frontend: generación masiva
**Tareas**
1. `features/batch`: botón de descarga de plantilla; zona de arrastrar y soltar con validación de extensión y tamaño en cliente.
2. Paso 1: enviar a `/validate`, mostrar resumen y tabla (shadcn `DataTable`) con filtros (RF-13).
3. Paso 2: selección de formatos y opciones; enviar a `/generate` y descargar el ZIP (RF-14). Indicador de progreso indeterminado con mensaje "Generando N códigos…".
4. Manejo de errores: archivo rechazado, límite excedido, rate limit, timeout.

**Criterios de aceptación**
- Flujo completo funciona desde Vercel con los fixtures de la Fase 5.
- Las filas con error se distinguen visualmente y el mensaje explica cómo corregirlas.
- El botón "Generar" se deshabilita si no hay filas válidas.

### Fase 7 — Endurecimiento y documentación
**Tareas**
1. Revisión de seguridad contra RNF-09 a RNF-14.
2. Revisión de accesibilidad (Lighthouse ≥ 90 en Accesibilidad).
3. Verificar cobertura (RNF-15) y que el CI falle si baja del umbral.
4. README completo: descripción, capturas, cómo correr en local, variables de entorno, despliegue, límites del plan gratuito, mediciones, cómo agregar una simbología nueva.
5. Etiquetar versión `v1.0.0`.

**Criterios de aceptación**
- Todos los RF y RNF de este documento verificados (marcar checklist en el README o en un issue).
- Lighthouse Accesibilidad ≥ 90, Performance ≥ 85 en la URL de Vercel.

### Fase 8 — Futuro (no implementar sin aprobación)
- Nuevas simbologías: EAN-8, UPC-A, Code 128, QR, ITF-14, DataMatrix (registrar en `SymbologyRegistry`).
- Nuevos formatos: SVG y PDF (BWIPP/Ghostscript los soporta).
- Hojas de etiquetas PDF para impresión.
- Si el plan gratuito queda corto: Render Starter o Cloud Run, y procesamiento asíncrono de lotes grandes.

---

## 7. Checklist de verificación final

- [ ] RF-01 a RF-23 implementados y probados
- [ ] RNF-01 a RNF-26 cumplidos
- [ ] PNG decodificables con `zxing-cpp`; EPS vectoriales verificados en Inkscape/Illustrator
- [ ] Sin escrituras a disco en runtime
- [ ] CORS restringido y rate limiting activo en producción
- [ ] Warm-up y estado del servidor funcionando con el backend dormido
- [ ] Límites medidos en Render y documentados
- [ ] CI en verde; deploy automático en Vercel y Render
