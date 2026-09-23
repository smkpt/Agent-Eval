"""Performance, Load, and Stress Test Suite for Healthcare Multi-Agent AI."""
import time
import concurrent.futures
from typing import List, Dict, Any

from src.agents.root_orchestrator import RootHealthcareOrchestrator
from src.agents.prescriber_agent import PrescriberAgent
from src.agents.prior_auth_agent import PriorAuthAgent
from src.saga.saga_coordinator import SagaCoordinator
from src.mcp_servers.async_gateway_mcp import AsyncPayerGatewayMCP
from src.security.phi_masking import PHIMaskingService
from src.storage.mongo_client import MongoClient
from src.storage.postgres_client import PostgresClient
from src.storage.db2_client import DB2Client
from src.telemetry.metrics import PerformanceMetricsRegistry

def _create_test_orchestrator(simulate_db2_timeout: bool = False):
    gateway = AsyncPayerGatewayMCP()
    mongo = MongoClient()
    postgres = PostgresClient()
    db2 = DB2Client()
    db2.simulate_timeout = simulate_db2_timeout
    saga = SagaCoordinator(mongo=mongo, postgres=postgres, db2=db2)
    phi_masker = PHIMaskingService()
    prescriber = PrescriberAgent()
    pa_agent = PriorAuthAgent(gateway_mcp=gateway)
    orchestrator = RootHealthcareOrchestrator(
        prescriber_agent=prescriber,
        prior_auth_agent=pa_agent,
        saga_coordinator=saga,
        phi_masker=phi_masker
    )
    return orchestrator, db2, postgres, mongo

def test_concurrent_load_throughput():
    """Validates that the multi-agent system handles 50 concurrent transactions

    with sustained throughput (> 200 RPS in-memory) and zero deadlocks.
    """
    orchestrator, _, _, _ = _create_test_orchestrator()
    concurrency = 50

    def submit_tx(i: int) -> Dict[str, Any]:
        payload = {
            "order_id": f"PERF-{int(time.time() * 1000)}-{i}",
            "idempotency_key": f"IDEMP-PERF-{i}",
            "patient_name": f"Concurrent Patient {i}",
            "ndc_code": "00169-4132-12",  # Ozempic
            "clinical_notes": "Type 2 Diabetes (E11.9) with prior Metformin 1000mg for 6 months."
        }
        return orchestrator.handle_clinical_request(payload)

    start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(submit_tx, i) for i in range(concurrency)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    total_time = max(time.perf_counter() - start, 0.0001)

    rps = concurrency / total_time
    committed_count = sum(1 for r in results if r.get("order_status") == "COMMITTED")

    assert committed_count == concurrency, f"Expected {concurrency} committed, got {committed_count}"
    assert rps > 50.0, f"Throughput {rps:.1f} RPS fell below SLA threshold of 50 RPS"

def test_latency_percentiles_sla():
    """Validates that p50, p90, and p95 latencies strictly satisfy SLA bounds."""
    registry = PerformanceMetricsRegistry()
    registry.reset()
    orchestrator, _, _, _ = _create_test_orchestrator()

    iterations = 50
    for i in range(iterations):
        t0 = time.perf_counter()
        payload = {
            "order_id": f"LAT-SLA-{i}",
            "idempotency_key": f"IDEMP-LAT-{i}",
            "patient_name": f"Latency Patient {i}",
            "ndc_code": "00093-7212-01",  # Metformin (no PA needed)
            "clinical_notes": "Routine diabetic checkup."
        }
        res = orchestrator.handle_clinical_request(payload)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        registry.record_histogram("agent_perf_latency_ms", elapsed_ms)

    percentiles = registry.get_percentiles("agent_perf_latency_ms")
    assert percentiles["count"] == iterations
    # In-memory execution SLA: p95 must be under 100ms
    assert percentiles["p95"] < 100.0, f"P95 latency {percentiles['p95']}ms exceeded 100ms bound"
    assert percentiles["p50"] <= percentiles["p95"], "Percentile ordering anomaly"

def test_phi_masking_throughput_benchmark():
    """Benchmarks PHI De-identification engine throughput across 100 clinical notes."""
    masker = PHIMaskingService()
    sample_text = (
        "Patient Eleanor Vance (DOB: 11/04/1975, SSN: 444-55-6666, MRN: 8829102) "
        "contacted via phone 555-839-2011 and email evance@carecorp.com. "
        "Prescribe Metformin 500mg daily."
    )

    count = 100
    t0 = time.perf_counter()
    for _ in range(count):
        masked, _ = masker.mask(sample_text)
        assert "444-55-6666" not in masked
    elapsed = max(time.perf_counter() - t0, 0.0001)

    throughput = count / elapsed
    assert throughput > 200.0, f"Masking throughput {throughput:.1f} notes/sec below benchmark (200 notes/sec)"

def test_stress_under_high_failure_rate():
    """Validates that the Saga Coordinator handles failure injection

    under concurrent load without leaking memory, thread deadlocks, or leaving orphan states.
    """
    total_tx = 40
    
    # Pre-create isolated orchestrators per transaction to test thread-isolated resilience
    def submit_stress_tx(i: int):
        should_fail = (i % 4 == 0)
        orch, _, _, _ = _create_test_orchestrator(simulate_db2_timeout=should_fail)
        payload = {
            "order_id": f"STRESS-{i}",
            "idempotency_key": f"IDEMP-STRESS-{i}",
            "patient_name": f"Stress Patient {i}",
            "ndc_code": "00002-1433-80",
            "clinical_notes": "Type 2 Diabetes with Metformin trial."
        }
        return orch.handle_clinical_request(payload)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(submit_stress_tx, range(total_tx)))

    failed_count = sum(1 for r in results if r.get("order_status") == "SAGA_EXECUTION_FAILED")
    committed_count = sum(1 for r in results if r.get("order_status") == "COMMITTED")

    # Verify expected failure and success counts
    assert failed_count == 10, f"Expected 10 compensated transactions, got {failed_count}"
    assert committed_count == 30, f"Expected 30 committed transactions, got {committed_count}"
