# CLAUDE.md — Generador de Códigos de Barras

## Fuente de verdad
- `PLAN.md` define requerimientos (RF/RNF), arquitectura, contrato de API y fases.
- Implementa **una fase a la vez**, en orden. No adelantes trabajo de fases posteriores.
- Antes de cerrar una fase, verifica todos sus criterios de aceptación y reporta cuáles se cumplieron.
- Si algo del plan no es viable o es ambiguo, detente y explica las opciones antes de improvisar.

## Forma de trabajar
- Explica brevemente el *porqué* de cada decisión técnica relevante (el desarrollador quiere aprender mientras construye).
- Cambios pequeños y verificables; un commit por tarea lógica con mensajes convencionales (`feat:`, `fix:`, `test:`, `chore:`, `docs:`).
- Escribe los tests junto con el código, no al final.

## Convenciones
- Código (variables, funciones, clases, rutas) en **inglés**; textos de UI, mensajes al usuario y docs en **español**.
- Backend: Python 3.12, tipado completo, `ruff` + `mypy --strict`, `pytest`. Dependencias con `uv`.
- Frontend: TypeScript estricto, componentes shadcn, formularios con `react-hook-form` + `zod`, datos con TanStack Query.
- Frontend con `pnpm` (no npm) y `oxlint` (no ESLint).
- Tipos de la API en el front se generan con `pnpm gen:api`; no los edites a mano.

## Reglas que no se rompen
- **Nunca escribir archivos en disco en runtime** (Render tiene disco efímero). Todo en memoria (`io.BytesIO`).
- **EPS debe ser vectorial.** No usar `PIL.Image.save(..., "EPS")` (embebe un bitmap). Ver `PLAN.md` §5.3.
- Ghostscript siempre con `-dSAFER`, stdin/stdout y timeout.
- Generación de códigos (bloqueante) en threadpool.
- CORS solo con `ALLOWED_ORIGINS`; nunca `*` en producción.
- No registrar en logs los códigos ni el contenido de los archivos del usuario.
- Errores con el formato `{ "error": { "code", "message", "details" } }`.

## Comandos
```bash
# Local completo
docker compose up

# Backend
cd backend
uv sync
uv run uvicorn app.main:app --reload
uv run pytest --cov=app
uv run ruff check . && uv run ruff format --check . && uv run mypy app

# Frontend
cd frontend
pnpm install
pnpm dev
pnpm gen:api           # requiere backend en localhost:8000
pnpm lint && pnpm typecheck && pnpm test && pnpm build
```
