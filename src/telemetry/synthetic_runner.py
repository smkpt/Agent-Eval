"""Synthetic Canary Runner executing simulated clinical traffic for operational SLA validation."""
import time
from typing import Dict, Any, List
from src.agents.root_orchestrator import RootHealthcareOrchestrator
from src.agents.prescriber_agent import PrescriberAgent
from src.agents.prior_auth_agent import PriorAuthAgent
from src.saga.saga_coordinator import SagaCoordinator
from src.mcp_servers.async_gateway_mcp import AsyncPayerGatewayMCP
from src.security.phi_masking import PHIMaskingService
from src.storage.mongo_client import MongoClient
from src.storage.postgres_client import PostgresClient
from src.storage.db2_client import DB2Client
from src.telemetry.metrics import metrics_registry

class SyntheticCanaryRunner:
    """Simulates real-world patient and prescriber workflows to measure operations visibility."""

    def __init__(self):
        self.gateway = AsyncPayerGatewayMCP()
        self.mongo = MongoClient()
        self.postgres = PostgresClient()
        self.db2 = DB2Client()
        self.saga = SagaCoordinator(mongo=self.mongo, postgres=self.postgres, db2=self.db2)
        self.phi_masker = PHIMaskingService()
        self.prescriber = PrescriberAgent()
        self.pa_agent = PriorAuthAgent(gateway_mcp=self.gateway)
        self.orchestrator = RootHealthcareOrchestrator(
            prescriber_agent=self.prescriber,
            prior_auth_agent=self.pa_agent,
            saga_coordinator=self.saga,
            phi_masker=self.phi_masker
        )

    def run_canary_batch(self, count: int = 4) -> Dict[str, Any]:
        """Executes a round of synthetic clinical scenarios and records operational telemetry."""
        results = []
        start_time = time.time()

        for i in range(count):
            scenario_type = i % 4
            scenario_result = self._execute_scenario(scenario_type, i)
            results.append(scenario_result)

        total_duration_ms = (time.time() - start_time) * 1000.0
        passed_count = sum(1 for r in results if r["passed"])
        availability_pct = (passed_count / len(results)) * 100.0 if results else 0.0

        metrics_registry.set_gauge("synthetic_canary_availability_pct", availability_pct)

        return {
            "batch_size": len(results),
            "passed_count": passed_count,
            "failed_count": len(results) - passed_count,
            "availability_percentage": round(availability_pct, 2),
            "total_duration_ms": round(total_duration_ms, 2),
            "scenarios": results
        }

    def _execute_scenario(self, scenario_type: int, index: int) -> Dict[str, Any]:
        t0 = time.time()
        order_id = f"SYNTH-{int(time.time() * 1000)}-{index}"
        
        # Scenario 0: Happy Path (Step-Therapy Verified -> Approved & Committed)
        if scenario_type == 0:
            name = "Happy Path: E-Rx with Verified Step Therapy"
            payload = {
                "order_id": order_id,
                "idempotency_key": f"IDEMP-{order_id}",
                "patient_name": f"Synthetic Patient {index}",
                "ndc_code": "00169-4132-12",  # Ozempic
                "clinical_notes": "Type 2 Diabetes (E11.9) with prior Metformin trial 1000mg for 6 months."
            }
            res = self.orchestrator.handle_clinical_request(payload)
            passed = res.get("success") is True and res.get("order_status") == "COMMITTED"
            metrics_registry.increment_counter("saga_transactions_total", 1.0, {"status": "committed"})

        # Scenario 1: Unmet Criteria (Proper Clinical Denial)
        elif scenario_type == 1:
            name = "Clinical Rule: Unmet Step Therapy Criteria"
            payload = {
                "order_id": order_id,
                "idempotency_key": f"IDEMP-{order_id}",
                "patient_name": f"Synthetic Patient {index}",
                "ndc_code": "00169-4132-12",
                "clinical_notes": "Patient diagnosed with hypertension. No diabetes history."
            }
            res = self.orchestrator.handle_clinical_request(payload)
            passed = res.get("success") is False and res.get("order_status") == "DENIED_PRIOR_AUTH"
            metrics_registry.increment_counter("prior_auth_denied_total", 1.0)

        # Scenario 2: Mainframe DB2 Failure & Clean Compensation
        elif scenario_type == 2:
            name = "Resilience: DB2 Timeout & Saga Rollback"
            self.db2.simulate_timeout = True
            payload = {
                "order_id": order_id,
                "idempotency_key": f"IDEMP-{order_id}",
                "patient_name": f"Synthetic Patient {index}",
                "ndc_code": "00002-1433-80",
                "clinical_notes": "Type 2 Diabetes with Metformin trial."
            }
            res = self.orchestrator.handle_clinical_request(payload)
            # Must properly compensate and prevent orphan records
            passed = res.get("success") is False and res.get("order_status") == "SAGA_EXECUTION_FAILED"
            self.db2.simulate_timeout = False
            metrics_registry.increment_counter("saga_transactions_total", 1.0, {"status": "compensated"})
            metrics_registry.increment_counter("db_timeout_total", 1.0, {"datastore": "db2"})

        # Scenario 3: Duplicate Request / Idempotency Collision
        else:
            name = "Concurrency: Idempotency Lock Enforcement"
            shared_key = f"IDEMP-SHARED-{order_id}"
            self.postgres.acquire_idempotency_lock(shared_key)
            payload = {
                "order_id": order_id,
                "idempotency_key": shared_key,
                "patient_name": f"Synthetic Patient {index}",
                "ndc_code": "00093-7212-01",
                "clinical_notes": "Standard metformin prescription."
            }
            res = self.orchestrator.handle_clinical_request(payload)
            passed = res.get("success") is False and res.get("order_status") == "SAGA_EXECUTION_FAILED"
            self.postgres.release_idempotency_lock(shared_key)
            metrics_registry.increment_counter("idempotency_lock_conflicts_total", 1.0)

        duration_ms = (time.time() - t0) * 1000.0
        metrics_registry.record_histogram("agent_latency_ms", duration_ms, {"scenario": str(scenario_type)})
        metrics_registry.increment_counter("agent_requests_total", 1.0, {"passed": str(passed)})

        return {
            "scenario": name,
            "order_id": order_id,
            "passed": passed,
            "duration_ms": round(duration_ms, 2)
        }
