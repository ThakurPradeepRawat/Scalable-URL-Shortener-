"""
Load test matching realistic production traffic shape: reads
(redirects) vastly outnumber writes (shortens), roughly 100:1 in
practice. Weighted 19:1 here is close enough to reproduce the
cache-hit-rate and latency numbers documented in the README.

Usage:
    locust -f loadtest/locustfile.py --host http://localhost:8000

Headless, matching the documented benchmark run:
    locust -f loadtest/locustfile.py --host http://localhost:8000 \\
        --users 5000 --spawn-rate 100 --run-time 5m --headless \\
        --csv=loadtest/results
"""
import random
import string

from locust import HttpUser, between, task

# A fixed pool of pre-shortened codes is used for the redirect task so
# that repeated requests hit the same "hot" links -- this is what lets
# Redis's LRU cache actually demonstrate a realistic hit rate, instead
# of every request being a guaranteed cold miss against fresh codes.
_KNOWN_SHORT_CODES: list[str] = []


class ShortenerUser(HttpUser):
    wait_time = between(0.1, 1.0)

    def on_start(self):
        # Seed a handful of short URLs once per simulated user so there
        # is something to redirect against from request one.
        if len(_KNOWN_SHORT_CODES) < 200:
            self._create_short_url()

    @task(19)
    def redirect(self):
        if not _KNOWN_SHORT_CODES:
            self._create_short_url()
            return

        code = random.choice(_KNOWN_SHORT_CODES)
        with self.client.get(f"/{code}", allow_redirects=False, catch_response=True) as resp:
            if resp.status_code in (302, 301):
                resp.success()
            else:
                resp.failure(f"Unexpected status {resp.status_code}")

    @task(1)
    def shorten(self):
        self._create_short_url()

    def _create_short_url(self):
        random_path = "".join(random.choices(string.ascii_lowercase, k=12))
        payload = {"long_url": f"https://example.com/{random_path}"}

        with self.client.post("/api/shorten", json=payload, catch_response=True) as resp:
            if resp.status_code == 201:
                resp.success()
                _KNOWN_SHORT_CODES.append(resp.json()["short_code"])
            else:
                resp.failure(f"Unexpected status {resp.status_code}")
