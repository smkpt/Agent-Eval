"""Locust Load & Performance Test Suite for Healthcare Multi-Agent AI."""
import random
import time
from locust import HttpUser, task, between, tag

class PrescriberWorkflowUser(HttpUser):
    """Simulates healthcare providers issuing complex e-prescriptions requiring

    asynchronous prior authorization (HTTP 202) and multi-store Saga commits.
    """
    wait_time = between(0.1, 0.5)

    @tag("prior_auth", "e_rx")
    @task(3)
    def submit_complex_prescription(self):
        order_num = random.randint(10000, 99999)
        payload = {
            "order_id": f"LOCUST-RX-{order_num}",
            "idempotency_key": f"IDEMP-LOCUST-{order_num}",
            "patient_name": f"Locust Patient {order_num}",
            "ndc_code": "00169-4132-12",  # Ozempic 2mg/3mL (requires prior auth)
            "sig": "0.5mg injected subcutaneously once weekly",
            "clinical_notes": (
                "Patient diagnosed with Type 2 Diabetes mellitus (E11.9). "
                "Documented trial of first-line Metformin 1000mg BID for 6 months."
            )
        }
        with self.client.post("/api/v1/prescriptions", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("order_status") == "COMMITTED":
                    response.success()
                else:
                    response.failure(f"Unexpected status: {data.get('order_status')}")
            else:
                response.failure(f"HTTP {response.status_code}: {response.text}")


class MaintenanceRefillUser(HttpUser):
    """Simulates rapid high-throughput formulary refills (no prior authorization required)."""
    wait_time = between(0.05, 0.2)

    @tag("refill", "fast_path")
    @task(5)
    def submit_fast_refill(self):
        order_num = random.randint(10000, 99999)
        payload = {
            "order_id": f"REFILL-{order_num}",
            "idempotency_key": f"IDEMP-REFILL-{order_num}",
            "patient_name": f"Refill Patient {order_num}",
            "ndc_code": "00093-7212-01",  # Metformin 500mg (Tier 1, no PA)
            "sig": "Take 1 tablet daily with meals",
            "clinical_notes": "Routine 90-day maintenance refill."
        }
        with self.client.post("/api/v1/prescriptions", json=payload, catch_response=True) as response:
            if response.status_code == 200 and response.json().get("order_status") == "COMMITTED":
                response.success()
            else:
                response.failure(f"Failed fast refill: {response.text}")


class AdversarialPIIUser(HttpUser):
    """Stress-tests the Presidio HIPAA De-Identification engine with high volumes

    of unmasked PII/PHI payloads to verify zero-leakage and measure sanitization overhead.
    """
    wait_time = between(0.2, 0.8)

    @tag("security", "hipaa")
    @task(2)
    def submit_unmasked_phi_payload(self):
        ssn = f"{random.randint(100,999)}-{random.randint(10,99)}-{random.randint(1000,9999)}"
        phone = f"555-{random.randint(100,999)}-{random.randint(1000,9999)}"
        order_num = random.randint(10000, 99999)
        
        payload = {
            "order_id": f"PHI-STRESS-{order_num}",
            "idempotency_key": f"IDEMP-PHI-{order_num}",
            "patient_name": f"Johnathan Q. Doe {order_num}",
            "ndc_code": "00002-1433-80",  # Trulicity
            "clinical_notes": (
                f"Patient Johnathan Doe (SSN: {ssn}, Phone: {phone}, DOB: 05/14/1972) "
                f"living at 90210. Evaluated for Type 2 Diabetes with prior Metformin usage."
            )
        }
        with self.client.post("/api/v1/prescriptions", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                summary = response.json().get("sanitized_summary", "")
                if ssn in summary or phone in summary or "Johnathan" in summary:
                    response.failure(f"CRITICAL: Unmasked PHI leaked into response: {summary}")
                else:
                    response.success()
            else:
                response.failure(f"HTTP {response.status_code}: {response.text}")


class ObservabilityScraperUser(HttpUser):
    """Simulates Dynatrace and Prometheus scrapers polling health and metrics endpoints."""
    wait_time = between(0.5, 1.5)

    @tag("observability", "metrics")
    @task(2)
    def scrape_prometheus_metrics(self):
        with self.client.get("/metrics", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Prometheus scrape failed: {response.status_code}")

    @tag("observability", "health")
    @task(1)
    def poll_health_diagnostics(self):
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200 and response.json().get("system_status") in ["HEALTHY", "DEGRADED"]:
                response.success()
            else:
                response.failure(f"Health check failed: {response.text}")
