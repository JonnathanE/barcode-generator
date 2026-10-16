from app.core.errors import AppError, ErrorCode
from app.symbologies.base import Symbology
from app.symbologies.ean13 import Ean13


class SymbologyRegistry:
    def __init__(self) -> None:
        self._by_id: dict[str, Symbology] = {}

    def register(self, symbology: Symbology) -> None:
        if symbology.id in self._by_id:
            raise ValueError(f"symbology {symbology.id!r} already registered")
        self._by_id[symbology.id] = symbology

    def get(self, symbology_id: str) -> Symbology:
        try:
            return self._by_id[symbology_id]
        except KeyError:
            raise AppError(
                ErrorCode.UNSUPPORTED_SYMBOLOGY,
                f"La simbología «{symbology_id}» no está soportada.",
                {"supported": list(self._by_id)},
            ) from None

    def all(self) -> list[Symbology]:
        return list(self._by_id.values())


registry = SymbologyRegistry()
registry.register(Ean13())
