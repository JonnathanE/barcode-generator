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

Opciones por defecto: escala 2, 300 DPI, con texto. El piso de cada llamada es el arranque de Ghostscript (~0,4 s con 0,1 CPU). El EPS pesa 171 KB porque `eps2write` siempre incluye su prolog genérico (~165 KB); el dibujo en sí ocupa ~9 KB, y comprimido en ZIP el archivo baja a ~46 KB.

## Estado

En construcción: Fase 1 (spike de generación PNG + EPS vectorial).
