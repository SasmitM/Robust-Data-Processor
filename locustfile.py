from locust import HttpUser, task, between
import random
import uuid

class LogIngestionUser(HttpUser):
    wait_time = between(0.01, 0.05)  # 10-50ms between requests
    
    @task(3)
    def ingest_json(self):
        tenants = ["acme_corp", "beta_inc", "gamma_solutions"]
        self.client.post("/ingest",
            json={
                "tenant_id": random.choice(tenants),
                "log_id": f"load-{uuid.uuid4()}",
                "text": f"Load test entry with data: {random.randint(1000, 9999)}"
            },
            headers={"Content-Type": "application/json"}
        )
    
    @task(1)
    def ingest_text(self):
        tenants = ["acme_corp", "beta_inc"]
        self.client.post("/ingest",
            data="Plain text load test log entry",
            headers={
                "Content-Type": "text/plain",
                "X-Tenant-ID": random.choice(tenants)
            }
        )
