"""Unit tests for the VID generator (PRD §4.10)."""
import re

from main.app.core.vid import VID_ALPHABET, VID_SUFFIX_LENGTH, generate_vid

_ALPHABET_SET = set(VID_ALPHABET)


class TestVidFormat:
    def test_shape_with_explicit_year(self):
        vid = generate_vid(2026)
        assert vid.startswith("VP-2026-")
        prefix, year, suffix = vid.split("-")
        assert prefix == "VP"
        assert year == "2026"
        assert len(suffix) == VID_SUFFIX_LENGTH

    def test_suffix_uses_only_unambiguous_alphabet(self):
        for _ in range(200):
            suffix = generate_vid(2026).split("-")[2]
            assert set(suffix) <= _ALPHABET_SET

    def test_alphabet_excludes_ambiguous_chars(self):
        for ambiguous in ("I", "L", "O", "U", "0", "1"):
            assert ambiguous not in VID_ALPHABET

    def test_regex_shape(self):
        assert re.fullmatch(r"VP-\d{4}-[A-Z2-9]{6}", generate_vid(2026))

    def test_defaults_to_current_year(self):
        from datetime import datetime, timezone
        assert generate_vid().split("-")[1] == f"{datetime.now(timezone.utc).year:04d}"


class TestVidNonSequential:
    def test_unique_over_many_calls(self):
        vids = {generate_vid(2026) for _ in range(2000)}
        # Collisions are astronomically unlikely; allow a tiny margin but expect ~all unique.
        assert len(vids) >= 1995

    def test_not_a_counter(self):
        # Consecutive VIDs must not be monotonically increasing like a sequence.
        suffixes = [generate_vid(2026).split("-")[2] for _ in range(50)]
        assert suffixes != sorted(suffixes)
