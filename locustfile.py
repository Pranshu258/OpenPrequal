import json
import os
from collections import Counter
from datetime import datetime

from locust import FastHttpUser, between, task


def get_log_file_name():
    algorithm = os.environ.get("ALGORITHM_NAME")
    if algorithm:
        return f"logs/{algorithm}_locust_backend_distribution.log"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"logs/locust_backend_distribution_{timestamp}.log"


class WebsiteUser(FastHttpUser):
    wait_time = between(1, 5)

    def on_start(self):
        # Use a single base log file for all requests
        self.log_file = get_log_file_name()

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
            # Log the backend used for this request on a new line
            with open(self.log_file, "a") as f:
                f.write(backend_id + "\n")
