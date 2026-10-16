import pytest

from app.core.errors import AppError, ErrorCode
from app.domain.ean13 import clean, compute_check_digit, normalize

# Non-ASCII digits that str.isdigit() accepts but EAN-13 must reject.
FULLWIDTH = "".join(chr(0xFF10 + int(d)) for d in "786123456789")
ARABIC_INDIC = "".join(chr(0x0660 + int(d)) for d in "786123456789")


class TestClean:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("786-1234-56789", "786123456789"),
            ("  7861234567898  ", "7861234567898"),
            ("786 1234 5678 98", "7861234567898"),
            ("7861234567898", "7861234567898"),
            ("-786\t123\n456789-", "786123456789"),
            ("", ""),
        ],
    )
    def test_removes_spaces_and_hyphens_anywhere(self, raw: str, expected: str) -> None:
        assert clean(raw) == expected


class TestComputeCheckDigit:
    @pytest.mark.parametrize(
        ("body", "expected"),
        [
            ("786123456789", 8),
            ("400638133393", 1),  # 4006381333931, common reference example
            ("978030640615", 7),  # ISBN 978-0-306-40615-7
            ("000000000000", 0),
            ("590123412345", 7),  # GS1 example 5901234123457
        ],
    )
    def test_known_codes(self, body: str, expected: int) -> None:
        assert compute_check_digit(body) == expected

    @pytest.mark.parametrize("body", ["12345678901", "1234567890123", "78612345678a", FULLWIDTH])
    def test_rejects_malformed_body(self, body: str) -> None:
        with pytest.raises(ValueError, match="12 ASCII digits"):
            compute_check_digit(body)


class TestNormalize:
    def test_twelve_digits_appends_check_digit(self) -> None:
        assert normalize("786123456789") == "7861234567898"

    def test_thirteen_digits_with_valid_check_digit_is_returned(self) -> None:
        assert normalize("7861234567898") == "7861234567898"

    def test_separators_are_ignored(self) -> None:
        assert normalize("786-1234-56789") == "7861234567898"

    def test_leading_zeros_are_preserved(self) -> None:
        assert normalize("000000000000") == "0000000000000"

    def test_wrong_check_digit_reports_expected_digit(self) -> None:
        with pytest.raises(AppError) as exc_info:
            normalize("7861234567897")

        error = exc_info.value
        assert error.code is ErrorCode.INVALID_CHECK_DIGIT
        assert error.message == "El dígito de control debe ser 8."
        assert error.details == {"expected": 8, "received": 7}
        assert error.status_code == 422

    @pytest.mark.parametrize(
        ("raw", "invalid"),
        [
            ("78612345678A", ["A"]),
            ("786.123.456.789", ["."]),
            ("786_123_456_78x", ["_", "x"]),
            ("78612345678²", ["²"]),  # Unicode digit, not ASCII
            (ARABIC_INDIC, sorted(set(ARABIC_INDIC))),
        ],
    )
    def test_non_digit_characters_are_rejected(self, raw: str, invalid: list[str]) -> None:
        with pytest.raises(AppError) as exc_info:
            normalize(raw)

        assert exc_info.value.code is ErrorCode.INVALID_CHARACTERS
        assert exc_info.value.details == {"invalid_characters": invalid}

    @pytest.mark.parametrize("raw", ["", "   ", "1", "78612345678", "78612345678981", "-" * 5])
    def test_wrong_length_is_rejected(self, raw: str) -> None:
        with pytest.raises(AppError) as exc_info:
            normalize(raw)

        error = exc_info.value
        assert error.code is ErrorCode.INVALID_LENGTH
        assert error.details["length"] == len(clean(raw))
        assert f"tiene {len(clean(raw))}" in error.message

    def test_characters_are_checked_before_length(self) -> None:
        with pytest.raises(AppError) as exc_info:
            normalize("abc")

        assert exc_info.value.code is ErrorCode.INVALID_CHARACTERS


def test_app_error_serializes_to_api_format() -> None:
    error = AppError(ErrorCode.INVALID_CHECK_DIGIT, "El dígito de control debe ser 8.", {"x": 1})

    assert error.to_dict() == {
        "error": {
            "code": "INVALID_CHECK_DIGIT",
            "message": "El dígito de control debe ser 8.",
            "details": {"x": 1},
        }
    }
