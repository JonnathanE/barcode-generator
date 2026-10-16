"""Spike de la Fase 1: genera PNG y EPS de ejemplo y mide tiempos.

Solo para desarrollo: es lo único que escribe en disco, y fuera de ``app/``.

    uv run python -m scripts.spike_render [--runs N]
"""

import argparse
import statistics
import time
from collections.abc import Callable
from pathlib import Path

from app.services.renderer import RenderOptions, render_ean13_eps, render_ean13_png

CODE = "7861234567898"
OUT_DIR = Path(__file__).parent / "out"


def measure(label: str, render: Callable[[], bytes], runs: int) -> bytes:
    durations: list[float] = []
    for _ in range(runs):
        start = time.perf_counter()
        data = render()
        durations.append(time.perf_counter() - start)
    print(
        f"{label}: {len(data) / 1024:.1f} KB · "
        f"mediana {statistics.median(durations):.2f} s · "
        f"min {min(durations):.2f} s · max {max(durations):.2f} s ({runs} ejecuciones)"
    )
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()

    options = RenderOptions()
    OUT_DIR.mkdir(exist_ok=True)

    png = measure("PNG", lambda: render_ean13_png(CODE, options), args.runs)
    eps = measure("EPS", lambda: render_ean13_eps(CODE, options), args.runs)

    (OUT_DIR / f"{CODE}.png").write_bytes(png)
    (OUT_DIR / f"{CODE}.eps").write_bytes(eps)
    print(f"Archivos en {OUT_DIR}/")


if __name__ == "__main__":
    main()
