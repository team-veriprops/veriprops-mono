"""Unit tests for the evidence content-hash helper (PRD §4.5)."""
import hashlib

import pytest

from main.app.core.evidence import compute_content_hash, verify_content_hash


class TestComputeContentHash:
    def test_known_vector(self):
        # SHA-256("") is a well-known constant.
        assert compute_content_hash(b"") == (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )

    def test_matches_hashlib(self):
        data = b"survey-plan-v1.pdf-bytes"
        assert compute_content_hash(data) == hashlib.sha256(data).hexdigest()

    def test_rejects_non_bytes(self):
        with pytest.raises(TypeError):
            compute_content_hash("not-bytes")  # type: ignore[arg-type]

    def test_accepts_bytearray(self):
        assert compute_content_hash(bytearray(b"abc")) == compute_content_hash(b"abc")


class TestVerifyContentHash:
    def test_matching_hash_verifies(self):
        data = b"original-evidence"
        assert verify_content_hash(data, compute_content_hash(data)) is True

    def test_case_insensitive_expected(self):
        data = b"original-evidence"
        assert verify_content_hash(data, compute_content_hash(data).upper()) is True

    def test_single_byte_change_detected(self):
        original = b"original-evidence"
        tampered = b"original-evidencE"
        stored = compute_content_hash(original)
        assert verify_content_hash(tampered, stored) is False

    def test_malformed_expected_is_false_not_raise(self):
        assert verify_content_hash(b"x", "deadbeef") is False
        assert verify_content_hash(b"x", "") is False
