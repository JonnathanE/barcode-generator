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

```bash
docker compose up
```

- Backend: http://localhost:8000 (`/health`, `/docs`)
- Frontend: http://localhost:5173

## Estado

En construcción: Fase 0 (esqueleto del monorepo).
