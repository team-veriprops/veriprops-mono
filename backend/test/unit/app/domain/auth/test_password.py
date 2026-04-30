"""Smoke tests for the password hashing path used by auth."""
from main.appodus_utils import Utils


def test_password_hash_round_trip():
    h = Utils.get_password_hash("Sup3rSecure!Pwd")
    assert Utils.verify_password("Sup3rSecure!Pwd", h) is True
    assert Utils.verify_password("wrong", h) is False


def test_password_hash_is_not_plaintext():
    pw = "PlaintextNeverWins!"
    h = Utils.get_password_hash(pw)
    assert h != pw
    assert pw not in h


def test_password_hash_is_unique_per_invocation():
    pw = "RepeatableInput123!"
    a = Utils.get_password_hash(pw)
    b = Utils.get_password_hash(pw)
    assert a != b
    # Both still verify.
    assert Utils.verify_password(pw, a)
    assert Utils.verify_password(pw, b)
