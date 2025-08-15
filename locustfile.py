import json
import os
from collections import Counter

from locust import HttpUser, TaskSet, between, task


class UserBehavior(TaskSet):
    backend_counter = Counter()
    log_file = "locust_backend_distribution.log"

    @task
    def health_check(self):
        with self.client.get("/", catch_response=True) as response:
            backend_id = response.headers.get("X-Backend-Id", "unknown")
            self.backend_counter[backend_id] += 1
            total = sum(self.backend_counter.values())
            if total % 100 == 0:
                dist = dict(self.backend_counter)
                print(f"Backend distribution: {dist}")
                # Append to log file as JSON
                with open(self.log_file, "a") as f:
                    f.write(json.dumps({"total": total, "distribution": dist}) + "\n")


class WebsiteUser(HttpUser):
    tasks = [UserBehavior]
    wait_time = between(1, 5)
