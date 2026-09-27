"""
Base62 encoding: [0-9][a-z][A-Z] -> 62 symbols.

Used to turn a monotonically increasing integer ID into a short,
URL-safe, non-sequential-looking code. 6 characters gives 62^6 ~= 56.8
billion addressable codes -- ~5,600x the 10M-URL design target -- with
zero collision handling required, unlike hash-based schemes.
"""

_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_BASE = len(_ALPHABET)
_INDEX = {char: i for i, char in enumerate(_ALPHABET)}


def encode(number: int, min_length: int = 0) -> str:
    """Encode a non-negative integer as a Base62 string.

    min_length left-pads with the zero symbol ('0') so codes have a
    consistent minimum width if desired (purely cosmetic -- uniqueness
    comes from the underlying integer, not the string length).
    """
    if number < 0:
        raise ValueError("base62.encode requires a non-negative integer")

    if number == 0:
        digits = [_ALPHABET[0]]
    else:
        digits = []
        n = number
        while n > 0:
            n, remainder = divmod(n, _BASE)
            digits.append(_ALPHABET[remainder])
        digits.reverse()

    encoded = "".join(digits)
    if len(encoded) < min_length:
        encoded = _ALPHABET[0] * (min_length - len(encoded)) + encoded
    return encoded


def decode(code: str) -> int:
    """Decode a Base62 string back into its integer ID.

    Raises ValueError on any character outside the Base62 alphabet --
    this is what lets the redirect handler distinguish "malformed code"
    (400) from "well-formed but unknown code" (404) if desired.
    """
    number = 0
    for char in code:
        if char not in _INDEX:
            raise ValueError(f"Invalid Base62 character: {char!r}")
        number = number * _BASE + _INDEX[char]
    return number
