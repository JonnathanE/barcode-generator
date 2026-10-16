"""EAN-13 input cleaning, check digit calculation and validation (RF-01 to RF-03)."""

import re

from app.core.errors import AppError, ErrorCode

BODY_LENGTH = 12
FULL_LENGTH = 13

_SEPARATORS = re.compile(r"[\s-]+")
# ASCII only: str.isdigit() would accept "²" or Arabic-Indic digits.
_NON_DIGIT = re.compile(r"[^0-9]")


def clean(raw: str) -> str:
    """Remove spaces and hyphens anywhere in the input (RF-03)."""
    return _SEPARATORS.sub("", raw)


def compute_check_digit(body: str) -> int:
    """GS1 mod-10 check digit for the 12-digit body.

    Weights alternate 1, 3, 1, 3... from the left; the check digit brings the
    weighted sum up to the next multiple of 10.
    """
    if len(body) != BODY_LENGTH or _NON_DIGIT.search(body):
        raise ValueError("body must be exactly 12 ASCII digits")
    total = sum(int(digit) * (3 if index % 2 else 1) for index, digit in enumerate(body))
    return (10 - total % 10) % 10


def normalize(raw: str) -> str:
    """Return the 13-digit code, computing or verifying the check digit (RF-01, RF-02)."""
    code = clean(raw)

    if invalid := sorted(set(_NON_DIGIT.findall(code))):
        raise AppError(
            ErrorCode.INVALID_CHARACTERS,
            "El código solo puede contener dígitos (se permiten espacios y guiones).",
            {"invalid_characters": invalid},
        )

    if len(code) not in (BODY_LENGTH, FULL_LENGTH):
        raise AppError(
            ErrorCode.INVALID_LENGTH,
            f"El código debe tener 12 o 13 dígitos; tiene {len(code)}.",
            {"length": len(code), "allowed": [BODY_LENGTH, FULL_LENGTH]},
        )

    expected = compute_check_digit(code[:BODY_LENGTH])
    if len(code) == BODY_LENGTH:
        return f"{code}{expected}"

    received = int(code[-1])
    if received != expected:
        raise AppError(
            ErrorCode.INVALID_CHECK_DIGIT,
            f"El dígito de control debe ser {expected}.",
            {"expected": expected, "received": received},
        )
    return code
