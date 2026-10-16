import pytest

from app.core.errors import AppError, ErrorCode
from app.symbologies.base import OutputFormat, RenderOptions
from app.symbologies.ean13 import Ean13
from app.symbologies.registry import SymbologyRegistry, registry


class TestEan13:
    def test_metadata(self) -> None:
        symbology = Ean13()

        assert (symbology.id, symbology.name, symbology.bwipp_name) == ("ean13", "EAN-13", "ean13")
        assert symbology.supported_formats == {OutputFormat.PNG, OutputFormat.EPS}

    def test_normalize_delegates_to_domain(self) -> None:
        assert Ean13().normalize("786-1234-56789") == "7861234567898"

    def test_bwipp_height_compensates_magnification(self) -> None:
        options = RenderOptions(bar_height_mm=25.4)

        bwipp = Ean13().bwipp_options(options, module_points=2.0)

        assert bwipp["height"] == "0.500000"  # 1 inch / magnification 2

    @pytest.mark.parametrize("include_text", [True, False])
    def test_text_and_whitespace_guard_go_together(self, include_text: bool) -> None:
        bwipp = Ean13().bwipp_options(RenderOptions(include_text=include_text), 1.0)

        assert bwipp["includetext"] is include_text
        assert bwipp["guardwhitespace"] is include_text

    def test_extent_includes_quiet_zones(self) -> None:
        without_text = Ean13().extent(RenderOptions(include_text=False), 1.0)
        with_text = Ean13().extent(RenderOptions(include_text=True), 1.0)

        assert (without_text.left, without_text.right, without_text.bottom) == (-11, 102, 0)
        assert without_text.width == 113
        assert (with_text.right, with_text.bottom) == (103, -10)

    def test_extent_top_is_bar_height_in_modules(self) -> None:
        extent = Ean13().extent(RenderOptions(bar_height_mm=25.4), module_points=2.0)

        assert extent.top == pytest.approx(36)  # 72 pt / 2 pt per module


class TestRegistry:
    def test_ean13_is_registered(self) -> None:
        assert registry.get("ean13").name == "EAN-13"
        assert [s.id for s in registry.all()] == ["ean13"]

    def test_unknown_symbology_raises_app_error(self) -> None:
        with pytest.raises(AppError) as exc_info:
            registry.get("qrcode")

        assert exc_info.value.code is ErrorCode.UNSUPPORTED_SYMBOLOGY
        assert exc_info.value.status_code == 404
        assert exc_info.value.details == {"supported": ["ean13"]}

    def test_duplicate_registration_is_rejected(self) -> None:
        local = SymbologyRegistry()
        local.register(Ean13())

        with pytest.raises(ValueError, match="already registered"):
            local.register(Ean13())
