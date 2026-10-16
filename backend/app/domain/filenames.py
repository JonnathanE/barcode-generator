"""Safe file names inside the ZIP (RNF-12) and collision handling (RF-16)."""

import re
import unicodedata

MAX_LENGTH = 100

# Path separators, characters Windows forbids, and control characters.
_UNSAFE = re.compile(r'[/\\<>:"|?*\x00-\x1f\x7f]')
_WHITESPACE = re.compile(r"\s+")
_ALPHANUMERIC = re.compile(r"[^\W_]")  # a letter or digit, in any script
_OUTPUT_EXTENSION = re.compile(r"\.(png|eps)$", re.IGNORECASE)
_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize(name: str) -> str | None:
    """Return a safe base name (without extension), or None if nothing usable remains."""
    cleaned = unicodedata.normalize("NFC", name)
    # Tabs and newlines become spaces before control characters are replaced.
    cleaned = _WHITESPACE.sub(" ", cleaned).strip()
    cleaned = _UNSAFE.sub("_", cleaned)
    cleaned = _OUTPUT_EXTENSION.sub("", cleaned)
    # Leading dots (hidden files) and trailing dots/spaces (invalid on Windows) go
    # first, then any remaining ".." (path traversal).
    cleaned = cleaned.strip(". ")
    cleaned = re.sub(r"\.{2,}", "_", cleaned)
    cleaned = cleaned[:MAX_LENGTH].rstrip(". ")
    if not _ALPHANUMERIC.search(cleaned):
        return None
    if cleaned.split(".")[0].upper() in _WINDOWS_RESERVED:
        cleaned = f"_{cleaned}"[:MAX_LENGTH]
    return cleaned


class FilenameAllocator:
    """Hands out unique names: ``name``, ``name_2``, ``name_3``…

    Comparison is case-insensitive because Windows and macOS file systems are, and
    two entries differing only in case would overwrite each other when unzipped.
    """

    def __init__(self) -> None:
        self._used: set[str] = set()

    def allocate(self, base: str) -> str:
        candidate = base
        suffix = 2
        while candidate.casefold() in self._used:
            tail = f"_{suffix}"
            candidate = f"{base[: MAX_LENGTH - len(tail)]}{tail}"
            suffix += 1
        self._used.add(candidate.casefold())
        return candidate
