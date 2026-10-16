from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.symbologies.base import TRANSPARENT, OutputFormat, RenderOptions

HexColor = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$"), AfterValidator(str.upper)]


def _normalize_background(value: str) -> str:
    return value if value == TRANSPARENT else value.upper()


# A single pattern (instead of a union) keeps validation errors on "background".
Background = Annotated[
    str,
    Field(pattern=r"^(#[0-9A-Fa-f]{6}|transparent)$"),
    AfterValidator(_normalize_background),
]

# Long enough for any symbology input plus separators; keeps payloads small.
CodeInput = Annotated[str, Field(max_length=64, examples=["786123456789"])]


class RenderOptionsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_text: bool = Field(True, description="Mostrar los dígitos bajo las barras.")
    scale: int = Field(
        2, ge=1, le=5, description="Magnificación física: el módulo mide 0,33 mm por la escala."
    )
    bar_height_mm: float = Field(22.85, ge=10, le=50, description="Altura final de las barras.")
    dpi: Literal[150, 300, 600] = Field(300, description="Resolución del PNG.")
    bar_color: HexColor = Field(
        "#000000", description="Color de barras y texto.", examples=["#000000"]
    )
    background: Background = Field(
        "#FFFFFF",
        description="Color de fondo (incluye la zona de silencio) o `transparent`.",
        examples=["#FFFFFF", TRANSPARENT],
    )

    def to_domain(self) -> RenderOptions:
        return RenderOptions(**self.model_dump())


class ValidateRequest(BaseModel):
    code: CodeInput


class ValidateResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"valid": True, "normalized": "7861234567898", "check_digit": 8}]
        }
    )

    valid: bool
    normalized: str
    check_digit: int


class RenderRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"code": "786123456789", "format": "png", "options": {"scale": 2, "dpi": 300}},
                {
                    "code": "7861234567898",
                    "format": "eps",
                    "options": {"bar_color": "#1F3A93", "background": TRANSPARENT},
                },
            ]
        }
    )

    code: CodeInput
    format: OutputFormat
    options: RenderOptionsIn = Field(default_factory=RenderOptionsIn)


class SymbologyOut(BaseModel):
    id: str = Field(examples=["ean13"])
    name: str = Field(examples=["EAN-13"])
    formats: list[OutputFormat]
