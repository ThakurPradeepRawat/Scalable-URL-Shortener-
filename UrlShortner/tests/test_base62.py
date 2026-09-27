import pytest

from app.core.base62 import decode, encode


@pytest.mark.parametrize(
    "number",
    [0, 1, 61, 62, 63, 12345, 999_999_999, 56_800_000_000],
)
def test_roundtrip(number):
    assert decode(encode(number)) == number


def test_encode_zero():
    assert encode(0) == "0"


def test_min_length_padding():
    assert encode(1, min_length=6) == "000001"
    assert len(encode(1, min_length=6)) == 6


def test_min_length_does_not_truncate_longer_codes():
    # min_length is a floor, never a ceiling
    big = 62**6 + 5
    assert len(encode(big, min_length=6)) > 6


def test_encoding_is_monotonic_in_length_class():
    # sanity check: larger numbers never produce a *shorter* string
    assert len(encode(1000)) >= len(encode(10))


def test_negative_raises():
    with pytest.raises(ValueError):
        encode(-1)


def test_decode_rejects_invalid_characters():
    with pytest.raises(ValueError):
        decode("abc!def")


def test_six_char_capacity_matches_design_target():
    # Design claim: 62^6 ~= 56.8 billion, comfortably above the 10M-URL target.
    capacity = 62**6
    assert capacity > 56_000_000_000
    assert capacity > 10_000_000 * 1000  # 1000x the 10M target
