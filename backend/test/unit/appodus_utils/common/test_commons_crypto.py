"""Security-token / OTP randomness (H4).

random_str and the random-mode OTP must be CSPRNG-backed (secrets), not the time-ordered
uuid7 or the non-crypto `random` module — both partially predictable.
"""
import os

from main.appodus_utils import Utils


class TestRandomStr:
    def test_exact_length_and_alphanumeric(self):
        for n in (1, 6, 8, 36, 48):
            s = Utils.random_str(n)
            assert len(s) == n
            assert s.isalnum()

    def test_high_uniqueness(self):
        # 200 draws of length 12 must be unique (a time-ordered/predictable generator
        # would collide or share long prefixes).
        values = {Utils.random_str(12) for _ in range(200)}
        assert len(values) == 200

    def test_no_shared_time_prefix(self):
        # uuid7's leading chars are a millisecond timestamp — two quick draws would share
        # a long common prefix. A CSPRNG string should not.
        a, b = Utils.random_str(12), Utils.random_str(12)
        common = 0
        for ca, cb in zip(a, b):
            if ca != cb:
                break
            common += 1
        assert common < 6


class TestOtpCode:
    def test_random_mode_is_six_digits(self):
        os.environ["OTP_MODE"] = "random"
        codes = {Utils.get_otp_code() for _ in range(20)}
        assert all(len(c) == 6 and c.isdigit() for c in codes)
        # 20 draws should not collapse to a single value.
        assert len(codes) > 1
