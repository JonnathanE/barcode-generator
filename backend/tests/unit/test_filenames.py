import pytest

from app.domain.filenames import MAX_LENGTH, FilenameAllocator, sanitize


class TestSanitize:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Leche entera 1L", "Leche entera 1L"),
            ("  café   con  leche  ", "café con leche"),
            ("../../x", "___x"),
            ("..\\..\\windows\\system32", "___windows_system32"),
            ("/etc/passwd", "_etc_passwd"),
            ("a/b\\c", "a_b_c"),
            ('pre<cio>:"x"|y?*', "pre_cio___x__y__"),
            ("tab\there\nnew", "tab here new"),
            ("null\x00byte\x1fend", "null_byte end"),
            (".oculto", "oculto"),
            ("final...", "final"),
            ("producto.png", "producto"),
            ("producto.EPS", "producto"),
            ("producto.jpg", "producto.jpg"),
            ("CON", "_CON"),
            ("nul.txt", "_nul.txt"),
            ("CONSOLA", "CONSOLA"),
        ],
    )
    def test_cleans_unsafe_names(self, raw: str, expected: str) -> None:
        assert sanitize(raw) == expected

    @pytest.mark.parametrize("raw", ["", "   ", "..", "...", "/", "\\\\", "..png", "*?"])
    def test_returns_none_when_nothing_usable_remains(self, raw: str) -> None:
        assert sanitize(raw) is None

    def test_limits_length(self) -> None:
        result = sanitize("a" * 300)

        assert result == "a" * MAX_LENGTH

    def test_normalizes_unicode(self) -> None:
        decomposed = "cafe\u0301"  # "e" + combining acute accent

        assert sanitize(decomposed) == "café"

    def test_never_returns_path_traversal(self) -> None:
        for raw in ["../../x", "..\\x", "a/../b", "....//....//"]:
            result = sanitize(raw)
            assert result is None or (
                "/" not in result and "\\" not in result and ".." not in result
            )


class TestFilenameAllocator:
    def test_unique_names_are_kept(self) -> None:
        allocator = FilenameAllocator()

        assert [allocator.allocate(n) for n in ["a", "b", "c"]] == ["a", "b", "c"]

    def test_collisions_get_numeric_suffixes(self) -> None:
        allocator = FilenameAllocator()

        names = [allocator.allocate("leche") for _ in range(3)]

        assert names == ["leche", "leche_2", "leche_3"]

    def test_collisions_are_case_insensitive(self) -> None:
        allocator = FilenameAllocator()

        assert [allocator.allocate(n) for n in ["Leche", "leche", "LECHE"]] == [
            "Leche",
            "leche_2",
            "LECHE_3",
        ]

    def test_suffix_does_not_collide_with_existing_name(self) -> None:
        allocator = FilenameAllocator()

        names = [allocator.allocate(n) for n in ["a_2", "a", "a"]]

        assert names == ["a_2", "a", "a_3"]

    def test_suffix_keeps_max_length(self) -> None:
        allocator = FilenameAllocator()
        long_name = "x" * MAX_LENGTH

        allocator.allocate(long_name)
        second = allocator.allocate(long_name)

        assert len(second) == MAX_LENGTH
        assert second.endswith("_2")
