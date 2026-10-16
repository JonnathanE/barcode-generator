from app.domain import ean13
from app.symbologies.base import (
    MM_PER_POINT,
    OutputFormat,
    RenderOptions,
    SymbolExtent,
)

# GS1 quiet zones (modules): 11 left, 7 right of the 95-module symbol.
_LEFT = -11
_RIGHT = 95 + 7
# With text, BWIPP draws the ">" whitespace guard just past the right quiet zone
# (~102.6) and the digits reach ~9.7 modules below the bars.
_RIGHT_WITH_TEXT = 103
_BOTTOM_WITH_TEXT = -10


class Ean13:
    id = "ean13"
    name = "EAN-13"
    bwipp_name = "ean13"
    module_mm = 0.33
    supported_formats = frozenset({OutputFormat.PNG, OutputFormat.EPS})

    def normalize(self, raw: str) -> str:
        return ean13.normalize(raw)

    def bwipp_options(self, options: RenderOptions, module_points: float) -> dict[str, str | bool]:
        # BWIPP's height is in inches and gets multiplied by the magnification
        # (one BWIPP module = 1 pt), so divide it out to get the physical height.
        height_in = options.bar_height_mm / 25.4 / module_points
        return {
            "includetext": options.include_text,
            "guardwhitespace": options.include_text,
            "height": f"{height_in:.6f}",
        }

    def extent(self, options: RenderOptions, module_points: float) -> SymbolExtent:
        top = options.bar_height_mm / MM_PER_POINT / module_points
        if options.include_text:
            return SymbolExtent(
                left=_LEFT, right=_RIGHT_WITH_TEXT, bottom=_BOTTOM_WITH_TEXT, top=top
            )
        return SymbolExtent(left=_LEFT, right=_RIGHT, bottom=0, top=top)
