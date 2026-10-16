from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

MM_PER_POINT = 25.4 / 72
TRANSPARENT = "transparent"


class OutputFormat(StrEnum):
    PNG = "png"
    EPS = "eps"

    @property
    def media_type(self) -> str:
        return _MEDIA_TYPES[self]


_MEDIA_TYPES = {OutputFormat.PNG: "image/png", OutputFormat.EPS: "application/postscript"}


@dataclass(frozen=True, slots=True)
class RenderOptions:
    include_text: bool = True
    scale: int = 2
    """Physical magnification: module width = ``Symbology.module_mm * scale``."""
    bar_height_mm: float = 22.85
    dpi: int = 300
    """PNG only."""
    bar_color: str = "#000000"
    """Bars and human-readable text, ``#RRGGBB``."""
    background: str = "#FFFFFF"
    """``#RRGGBB`` or ``"transparent"``; covers the quiet zones too."""


@dataclass(frozen=True, slots=True)
class SymbolExtent:
    """Area of the symbol including quiet zones, in modules.

    Relative to BWIPP's origin, which is the bottom-left corner of the bars.
    """

    left: float
    right: float
    bottom: float
    top: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.top - self.bottom


class Symbology(Protocol):
    id: str
    """URL identifier, e.g. ``"ean13"``."""
    name: str
    """Display name, e.g. ``"EAN-13"``."""
    bwipp_name: str
    module_mm: float
    """Nominal module width (X-dimension) at scale 1."""
    supported_formats: frozenset[OutputFormat]

    def normalize(self, raw: str) -> str:
        """Clean and validate user input; raises ``AppError`` when invalid."""
        ...

    def bwipp_options(self, options: RenderOptions, module_points: float) -> dict[str, str | bool]:
        """BWIPP options for this render; ``module_points`` is the module width in points."""
        ...

    def extent(self, options: RenderOptions, module_points: float) -> SymbolExtent: ...
