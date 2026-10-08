from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from api.v1.Routing.urls import get_short, make_short
from main import redirect_short
from schemas.urls import LongUrlRequest
from service.urls import (
    CounterUnavailableError,
    ShortUrlNotFoundError,
    decode_base62,
    encode_base62,
    reconcile_counter,
    shortUrlService,
)


class FakeRedis:
    def __init__(self):
        self.counter = 0
        self.values = {}

    def incr(self, key):
        self.counter += 1
        return self.counter

    def eval(self, script, key_count, key, target):
        current = self.values.get(key)
        if current is None or int(current) < int(target):
            self.values[key] = target
        return self.values[key]


class FakeRepo:
    def __init__(self):
        self.records = {}

    def Enter_short(self, long_url, short_code, *, url_id, expires_at=None):
        record = SimpleNamespace(
            id=url_id,
            short_code=short_code,
            long_url=long_url,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            is_active=True,
        )
        self.records[url_id] = record
        return record

    def Get_by_id(self, url_id):
        return self.records.get(url_id)

    def Deactivate(self, url_id, short_code):
        record = self.records.get(url_id)
        if record is None or record.short_code != short_code or not record.is_active:
            return False
        record.is_active = False
        return True


@pytest.mark.parametrize(
    ("url_id", "expected"),
    [(0, "0"), (9, "9"), (10, "a"), (35, "z"), (36, "A"), (61, "Z"), (62, "10")],
)
def test_base62_alphabet_vectors(url_id, expected):
    assert encode_base62(url_id) == expected
    assert decode_base62(expected) == url_id


@pytest.mark.parametrize("url_id", [1, 2**31 - 1, 2**53 + 1, 2**63 - 1])
def test_base62_round_trip_signed_64_bit_ids(url_id):
    assert decode_base62(encode_base62(url_id)) == url_id


@pytest.mark.parametrize("short_code", ["", "a-", "a b", "zzzzzzzzzzzz"])
def test_decode_rejects_invalid_codes(short_code):
    with pytest.raises(ValueError):
        decode_base62(short_code)


def test_counter_reconciliation_only_moves_forward():
    redis = FakeRedis()
    assert reconcile_counter(redis, 500) == 500
    redis.values["url_shortener:counter"] = "700"
    assert reconcile_counter(redis, 600) == 700


def test_create_uses_redis_counter_and_base62():
    redis = FakeRedis()
    repo = FakeRepo()
    service = shortUrlService(repo, redis)

    first = service.create_short_url(LongUrlRequest(long_url="https://example.com"))
    second = service.create_short_url(LongUrlRequest(long_url="https://example.org"))

    assert (first.id, first.short_code) == (1, "1")
    assert (second.id, second.short_code) == (2, "2")


def test_api_create_lookup_and_redirect_contract():
    service = shortUrlService(FakeRepo(), FakeRedis())
    request = LongUrlRequest(long_url="https://example.com/path")

    created = make_short(request, service)
    found = get_short(created.short_code, service)
    redirect = redirect_short(created.short_code, service)

    assert created.short_url.endswith(f"/r/{created.short_code}")
    assert found.long_url == request.long_url
    assert redirect.status_code == 307
    assert redirect.headers["location"] == request.long_url


def test_lookup_rejects_expired_or_deactivated_urls():
    service = shortUrlService(FakeRepo(), FakeRedis())
    expired = service.create_short_url(
        LongUrlRequest(
            long_url="https://example.com",
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=1),
        )
    )
    expired.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    with pytest.raises(ShortUrlNotFoundError):
        service.get_short_url(expired.short_code)

    active = service.create_short_url(LongUrlRequest(long_url="https://example.org"))
    assert service.delete_short_url(active.short_code)
    with pytest.raises(ShortUrlNotFoundError):
        service.get_short_url(active.short_code)


@pytest.mark.parametrize(
    "long_url",
    ["example.com", "ftp://example.com", "https://", "https://example.com:bad", "https://example.com/a b"],
)
def test_request_rejects_non_http_urls(long_url):
    with pytest.raises(ValueError):
        LongUrlRequest(long_url=long_url)


def test_expiration_must_be_in_the_future():
    with pytest.raises(ValueError):
        LongUrlRequest(
            long_url="https://example.com",
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )


def test_redis_allocation_failure_fails_closed():
    class BrokenRedis:
        def incr(self, key):
            raise ConnectionError("unavailable")

    service = shortUrlService(FakeRepo(), BrokenRedis())
    with pytest.raises(CounterUnavailableError):
        service.create_short_url(LongUrlRequest(long_url="https://example.com"))