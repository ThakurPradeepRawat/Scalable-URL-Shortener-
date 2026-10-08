from datetime import datetime, timezone
from typing import Any

from schemas.urls import LongUrlRequest

BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE62_LOOKUP = {character: index for index, character in enumerate(BASE62_ALPHABET)}
MAX_ID = 2**63 - 1
COUNTER_KEY = "url_shortener:counter"


class ShortUrlNotFoundError(Exception):
    pass


class CounterUnavailableError(Exception):
    pass


def encode_base62(value: int) -> str:
    if not isinstance(value, int) or value < 0 or value > MAX_ID:
        raise ValueError("ID must be an integer between 0 and 2^63 - 1")
    if value == 0:
        return BASE62_ALPHABET[0]

    encoded = []
    while value:
        value, remainder = divmod(value, len(BASE62_ALPHABET))
        encoded.append(BASE62_ALPHABET[remainder])
    return "".join(reversed(encoded))


def decode_base62(value: str) -> int:
    if not value:
        raise ValueError("Short code cannot be empty")

    decoded = 0
    for character in value:
        try:
            digit = BASE62_LOOKUP[character]
        except KeyError as error:
            raise ValueError("Short code contains a non-Base62 character") from error
        decoded = decoded * len(BASE62_ALPHABET) + digit
        if decoded > MAX_ID:
            raise ValueError("Short code exceeds the supported ID range")
    return decoded


def reconcile_counter(redis_client: Any, maximum_id: int, counter_key: str = COUNTER_KEY) -> int:
    if maximum_id < 0 or maximum_id > MAX_ID:
        raise ValueError("Maximum ID is outside the supported range")

    script = """
    local current = redis.call('GET', KEYS[1])
    local target = ARGV[1]
    if not current or #current < #target or (#current == #target and current < target) then
        redis.call('SET', KEYS[1], target)
        return target
    end
    return current
    """
    result = redis_client.eval(script, 1, counter_key, str(maximum_id))
    return int(result)


class shortUrlService:
    def __init__(self, repo: Any, redis_client: Any, counter_key: str = COUNTER_KEY):
        self.repo = repo
        self.redis = redis_client
        self.counter_key = counter_key

    def create_short_url(self, data: LongUrlRequest):
        try:
            url_id = int(self.redis.incr(self.counter_key))
        except Exception as error:
            raise CounterUnavailableError("Redis could not allocate a short-code ID") from error

        if url_id < 1 or url_id > MAX_ID:
            raise CounterUnavailableError("Redis allocated an ID outside the supported range")

        return self.repo.Enter_short(
            str(data.long_url),
            encode_base62(url_id),
            url_id=url_id,
            expires_at=data.expires_at,
        )

    def get_short_url(self, short_code: str):
        try:
            url_id = decode_base62(short_code)
        except ValueError as error:
            raise ShortUrlNotFoundError from error

        record = self.repo.Get_by_id(url_id)
        if record is None or record.short_code != short_code or not record.is_active:
            raise ShortUrlNotFoundError

        if record.expires_at is not None:
            expires_at = record.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= datetime.now(timezone.utc):
                raise ShortUrlNotFoundError
        return record

    def delete_short_url(self, short_code: str) -> bool:
        try:
            url_id = decode_base62(short_code)
        except ValueError:
            return False
        return self.repo.Deactivate(url_id, short_code)

