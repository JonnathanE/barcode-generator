"""Detect any file opened for writing in this process (RNF-07)."""

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

_write_opens: list[str] | None = None


def _audit(event: str, args: tuple[Any, ...]) -> None:
    if _write_opens is None or event != "open":
        return
    path, mode, flags = args
    if isinstance(path, int):
        return  # a file descriptor (e.g. the pipe to Ghostscript's stdin), not a file
    writes = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
        isinstance(flags, int) and flags & 0o3  # O_WRONLY | O_RDWR
    )
    if writes:
        _write_opens.append(str(path))


sys.addaudithook(_audit)  # audit hooks can't be removed; it's inert outside the context


@contextmanager
def no_disk_writes() -> Iterator[list[str]]:
    """Collect the paths opened for writing inside the block."""
    global _write_opens
    _write_opens = []
    try:
        yield _write_opens
    finally:
        _write_opens = None
