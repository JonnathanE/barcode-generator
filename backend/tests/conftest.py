from collections.abc import Iterator

import pytest

from app.core.rate_limit import limiter


@pytest.fixture(autouse=True)
def reset_rate_limits() -> Iterator[None]:
    """Each test starts with fresh per-IP counters."""
    limiter.reset()
    yield
