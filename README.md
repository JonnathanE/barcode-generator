# Generador de Códigos de Barras

Aplicación web para generar códigos de barras **EAN-13** listos para imprenta, en **PNG** y **EPS vectorial**, de forma individual o masiva desde Excel. Usa el motor open source [BWIPP](https://bwipp.terryburton.co.uk/) mediante `treepoem` y Ghostscript.

> ⚠️ Generar la imagen no otorga el derecho de usar el número en el comercio. Los códigos EAN-13 deben estar asignados por GS1 (en Ecuador, GS1 Ecuador).

## Estructura

```
backend/    API FastAPI (Python 3.12, uv)
frontend/   React + Vite + TypeScript (shadcn/ui)
```

El plan completo (requerimientos, arquitectura y fases) está en [`PLAN.md`](PLAN.md).

## Desarrollo local

Hay dos formas de levantar el proyecto: con **Docker** (recomendada, no requiere instalar Python ni Ghostscript) o **sin Docker**, corriendo cada servicio directamente en tu máquina.

### Opción A: Docker (recomendada)

**Requisitos:** [Docker](https://docs.docker.com/get-docker/) con Docker Compose v2 (`docker compose version`).

```bash
git clone https://github.com/JonnathanE/barcode-generator.git
cd barcode-generator
docker compose up --build
```

La primera vez tarda unos minutos (descarga imágenes, instala Ghostscript y las dependencias). Cuando veas el backend `healthy`, quedan disponibles:

| URL | Qué es |
|---|---|
| http://localhost:8000/docs | Swagger: documentación interactiva para probar la API |
| http://localhost:8000/health | Estado y versión del backend |
| http://localhost:5173 | Frontend (Vite) |

**¿Cuándo usar `--build`?** La primera vez y cada vez que cambien dependencias (`backend/pyproject.toml`, `backend/uv.lock` o `backend/Dockerfile`). Si solo cambias código, basta con `docker compose up`. El frontend instala sus dependencias (`pnpm install`) en cada arranque, así que no necesita reconstruirse: si cambian `frontend/package.json` o `pnpm-lock.yaml` (p. ej., tras un `git pull`), basta con `docker compose restart frontend`.

**Recarga automática:** el código se monta como volumen. Los cambios en `backend/app/` reinician uvicorn en uno o dos segundos y los cambios en `frontend/src/` se ven al instante en el navegador.

**Comandos útiles:**

```bash
docker compose up -d --build        # levantar en segundo plano
docker compose ps                   # estado de los servicios
docker compose logs -f backend      # logs JSON del backend en vivo
docker compose restart backend      # reiniciar (p. ej., tras editar backend/.env)
docker compose exec backend gs --version   # comando dentro del contenedor
docker compose down                 # apagar todo
docker compose down -v              # apagar y borrar el volumen de node_modules
```

#### Probar la API desde Swagger

1. Abre http://localhost:8000/docs.
2. Despliega `POST /api/v1/barcodes/{symbology}/render` y pulsa **Try it out**.
3. Escribe `ean13` en `symbology`, elige un ejemplo del cuerpo (o edítalo) y pulsa **Execute**.
4. El PNG se muestra en la respuesta; el EPS aparece como enlace de descarga.

O desde la terminal:

```bash
# Validar (calcula el dígito de control)
curl -X POST localhost:8000/api/v1/barcodes/ean13/validate \
  -H 'Content-Type: application/json' -d '{"code": "786-1234-56789"}'

# Generar un PNG con fondo transparente
curl -X POST localhost:8000/api/v1/barcodes/ean13/render \
  -H 'Content-Type: application/json' -o codigo.png \
  -d '{"code": "786123456789", "format": "png", "options": {"background": "transparent"}}'
```

### Opción B: sin Docker

**Requisitos:**

- [uv](https://docs.astral.sh/uv/getting-started/installation/) (descarga Python 3.12 por su cuenta; no hace falta instalarlo aparte).
- Ghostscript: `sudo apt install ghostscript` (Debian/Ubuntu/WSL) o `brew install ghostscript` (macOS). Verifica con `gs --version`.
- Node.js 24 y pnpm: `corepack enable` (activa la versión fijada en `package.json`) o [instálalo](https://pnpm.io/installation).

**Backend** (terminal 1):

```bash
cd backend
uv sync                                   # crea .venv con dependencias de desarrollo
uv run uvicorn app.main:app --reload      # http://localhost:8000
```

**Frontend** (terminal 2):

```bash
cd frontend
pnpm install
pnpm dev                                  # http://localhost:5173
```

### Variables de entorno

Todas tienen valores por defecto pensados para desarrollo, así que **no es necesario crear archivos `.env`** para empezar. Si quieres cambiar alguna:

```bash
cp backend/.env.example backend/.env       # luego edita los valores
cp frontend/.env.example frontend/.env     # solo para la Opción B
```

| Variable (backend) | Por defecto | Para qué sirve |
|---|---|---|
| `APP_ENV` | `development` | `development`, `test` o `production` (en producción se rechaza `ALLOWED_ORIGINS=*`) |
| `ALLOWED_ORIGINS` | `http://localhost:5173` | Orígenes permitidos por CORS, separados por comas |
| `RATE_LIMIT_SINGLE` | `60/minute` | Límite por IP de `validate` y `render`; súbelo si te bloquea al probar |
| `RATE_LIMIT_BATCH` | `5/minute` | Límite por IP del modo masivo |
| `MAX_UPLOAD_MB` / `MAX_BATCH_ROWS` | `2` / `500` | Límites del modo masivo |
| `GHOSTSCRIPT_TIMEOUT_SECONDS` | `20` | Tiempo máximo por llamada a Ghostscript |
| `LOG_LEVEL` | `INFO` | Nivel de los logs JSON |

En el frontend, `VITE_API_URL` (por defecto `http://localhost:8000`) indica dónde está el backend. Con Docker ya viene configurada en `docker-compose.yml`.

### Tests y calidad

```bash
# Backend dentro del contenedor (no requiere nada instalado localmente)
docker compose exec backend uv run pytest --cov=app

# Backend local (Opción B)
cd backend
uv run pytest --cov=app                   # tests + cobertura
uv run ruff check . && uv run ruff format --check . && uv run mypy app

# Frontend
cd frontend
pnpm lint && pnpm typecheck && pnpm format:check && pnpm build   # lint con oxlint
```

Los tests de generación necesitan Ghostscript; si no está instalado se omiten (aparecen como `skipped`).

Para generar archivos de muestra y medir tiempos: `cd backend && uv run python -m scripts.spike_render` (los deja en `backend/scripts/out/`, ignorado por git).

### Problemas comunes

| Síntoma | Solución |
|---|---|
| `port is already allocated` al levantar | Otro proceso usa el 8000 o el 5173. Detenlo, o cambia el puerto de la izquierda en `docker-compose.yml` (p. ej., `"8001:8000"`) |
| `ModuleNotFoundError` en el backend tras un `git pull` | Cambiaron dependencias: `docker compose up --build` (o `uv sync` sin Docker) |
| El frontend muestra una página en blanco o errores 500 de Vite tras un `git pull` | Cambiaron dependencias del frontend: `docker compose restart frontend` (o `pnpm install` sin Docker) |
| `Ghostscript (gs) no está instalado` | Opción B sin Ghostscript: instálalo (ver requisitos) |
| `429 RATE_LIMITED` mientras pruebas | Sube `RATE_LIMIT_SINGLE` en `backend/.env` y `docker compose restart backend` |
| El frontend no reacciona a cambios en WSL | Mantén el proyecto dentro del sistema de archivos de Linux (`~/...`), no en `/mnt/c/...` |

## Generación de PNG y EPS

El renderer (`backend/app/services/renderer.py`) usa la **Opción A** de `PLAN.md` §5.3: BWIPP en PostScript convertido con Ghostscript, todo en memoria (stdin/stdout, `-dSAFER` y timeout).

- **EPS vectorial:** `gs -sDEVICE=eps2write` aplana el programa BWIPP en trazos. El texto se convierte a contornos (`-dNoOutputFonts`), así el archivo no depende de que la imprenta tenga Helvetica. El tamaño físico es exacto: módulo = 0,33 mm × escala.
- **PNG:** se rasteriza directamente el programa BWIPP (`pnggray`) y se recorta con Pillow. El ancho de módulo se ajusta a píxeles enteros y se desactiva el `inkspread` de BWIPP, porque con módulos fraccionarios (p. ej., 1,95 px a 150 DPI) las barras salían irregulares y el código no se leía. Desviación máxima del tamaño físico: ~3 %.
- **Subconjunto de BWIPP:** solo se envían a Ghostscript los recursos que necesita la simbología, resueltos con los metadatos `--REQUIRES` (para EAN-13: ~56 KB en vez de 1 MB). Interpretar la biblioteca completa costaba ~10 s por llamada con 0,1 CPU.

> ¿Por qué no `treepoem.generate_barcode`? Llama a Ghostscript sin timeout, su `scale` es resolución (no tamaño físico) y devuelve una imagen de Pillow: guardarla como EPS embebe un bitmap. Del paquete solo se usa el `barcode.ps`.

### Mediciones (Fase 1)

`uv run python -m scripts.spike_render` genera `7861234567898.png` y `.eps` en `backend/scripts/out/` y mide los tiempos (mediana de 5). Medido en la imagen de producción (`--target runtime`), limitando la CPU con `docker run --cpus`:

| CPU | PNG (8,8 KB) | EPS (171 KB) |
|---|---|---|
| 1 CPU | 0,09 s | 0,08 s |
| 0,1 CPU (como Render free) | 1,11 s | 1,00 s |
| 0,1 CPU vía API (Fase 2) | ~1,1 s (escala 5 a 600 DPI: ~2 s) | ~1,0 s |

Opciones por defecto: escala 2, 300 DPI, con texto. El piso de cada llamada es el arranque de Ghostscript (~0,4 s con 0,1 CPU). El EPS pesa 171 KB porque `eps2write` siempre incluye su prolog genérico (~165 KB); el dibujo en sí ocupa ~9 KB, y comprimido en ZIP el archivo baja a ~46 KB.

## API

Documentación interactiva en `/docs` (Swagger). Todos los errores responden `{ "error": { "code", "message", "details" } }`.

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Estado y versión |
| GET | `/api/v1/symbologies` | Simbologías y formatos disponibles |
| POST | `/api/v1/barcodes/{symbology}/validate` | Normaliza y valida (`{"code": "786-1234-56789"}` → `7861234567898`) |
| POST | `/api/v1/barcodes/{symbology}/render` | PNG o EPS; `?inline=true` para la vista previa |

Opciones de `render` (todas opcionales):

| Opción | Valores | Por defecto |
|---|---|---|
| `include_text` | `true` / `false` | `true` |
| `scale` | 1–5 (módulo = 0,33 mm × escala; GS1 admite hasta 2) | `2` |
| `bar_height_mm` | 10–50 (altura final real) | `22.85` |
| `dpi` | 150, 300, 600 (solo PNG) | `300` |
| `bar_color` | `#RRGGBB` (barras y texto) | `#000000` |
| `background` | `#RRGGBB` o `transparent` | `#FFFFFF` |

Los archivos incluyen siempre la zona de silencio de EAN-13 (11 módulos a la izquierda y 7 a la derecha), pintada con el color de fondo.

## Despliegue

### Backend en Render

API pública: https://barcode-generator-api-yti8.onrender.com (`/health`, `/docs`).

El servicio se define en [`render.yaml`](render.yaml) (Blueprint): web service Docker gratuito en `virginia`, construido desde `backend/` (stage `runtime` del Dockerfile), con health check en `/health`.

- **Deploy automático:** cada push a `main` que cambie `backend/**` se despliega **solo si pasa el CI** (`autoDeployTrigger: checksPass`).
- **Variables:** las de `render.yaml`, más `ALLOWED_ORIGINS`, que se define en el panel de Render (Environment) y nunca en el repo.
- **IP real del cliente:** uvicorn corre con `--proxy-headers`, así el rate limit usa la IP de `X-Forwarded-For` y no la del proxy de Render.

Comandos útiles con el [CLI de Render](https://render.com/docs/cli):

```bash
render services                                       # servicios y URLs
render logs -r srv-db8q8drbc2fs73bq40bg --tail        # logs JSON en vivo
render deploys list srv-db8q8drbc2fs73bq40bg          # historial de deploys
render blueprints validate ./render.yaml              # validar el Blueprint
```

### CI

[`.github/workflows/backend.yml`](.github/workflows/backend.yml) corre en cada cambio de `backend/**`: ruff, mypy, pytest con Ghostscript (falla si la cobertura baja de 75 %) y una prueba de humo de la imagen Docker (`/health` y render PNG/EPS).

### Mediciones en Render (Fase 3)

Plan gratuito, región `virginia`, medido el 2026-10-16.

| Medición | Resultado |
|---|---|
| Render en el servidor (`duration_ms` de los logs, 23 muestras) | mediana **0,74 s** (mín. 0,67 s, máx. 1,48 s con escala 5 a 600 DPI) |
| Render visto desde el cliente (Ecuador, servidor despierto) | PNG ~1,1 s · EPS ~1,25 s (incluye ~0,35 s de red) |
| `/health` con el servidor despierto | ~0,4 s |
| **Cold start** (`/health` tras 17 min sin tráfico) | **22,5 s** (el contenedor arranca ~12 s después de la petición) |
| Primer render después del cold start | 1,3 s |

El cold start queda muy por debajo del timeout de 90 s del cliente (RNF-06). El frontend igual mostrará "Iniciando servidor…" mientras tanto (RF-20).

## Estado

En construcción: Fases 0 a 3 completas (backend desplegado en Render); sigue la Fase 4 (frontend individual y despliegue en Vercel).
