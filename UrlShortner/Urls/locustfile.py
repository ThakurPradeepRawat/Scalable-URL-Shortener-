from locust import HttpUser, task, between


class URLShortenerUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def create_short_url(self):
        response = self.client.post(
            "/urls/v1/",
            json={
                "long_url": "https://chatgpt.com/c/6abf38e2-7604-83ee-a7c2-67dd029c246a",
                "expires_at": "2026-10-08T07:14:02.583Z"
            }
        )

        if response.status_code not in (200, 201):
            print(
                "Create failed:",
                response.status_code,
                response.text
            )