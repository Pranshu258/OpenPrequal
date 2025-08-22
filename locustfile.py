import json
import os
from collections import Counter
from datetime import datetime

from locust import FastHttpUser, between, task


def get_log_file_name():
    algorithm = os.environ.get("ALGORITHM_NAME")
    if algorithm:
        return f"logs/locust_backend_distribution_{algorithm}.log"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"logs/locust_backend_distribution_{timestamp}.log"


class WebsiteUser(FastHttpUser):
    wait_time = between(1, 5)
    backend_counter = Counter()
    log_file = get_log_file_name()

    @task
    def health_check(self):
        with self.client.get("/", catch_response=True) as response:
            if (
                response is not None
                and hasattr(response, "headers")
                and response.headers is not None
            ):
                backend_id = response.headers.get("X-Backend-Id", "unknown")
            else:
                backend_id = "unknown"
            WebsiteUser.backend_counter[backend_id] += 1
            total = sum(WebsiteUser.backend_counter.values())
            if total % 100 == 0:
                dist = dict(WebsiteUser.backend_counter)
                # Append to log file as JSON
                with open(WebsiteUser.log_file, "a") as f:
                    f.write(json.dumps({"total": total, "distribution": dist}) + "\n")
