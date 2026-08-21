from locust import HttpUser, task, between

class ApiUser(HttpUser):
    # Each simulated user waits 0.1–0.5s between requests,
    # like a real client would, instead of hammering nonstop.
    wait_time = between(0.1, 0.5)

    @task
    def hit_work_endpoint(self):
        self.client.post("/work")