"""Universal test runner executing unit tests, guardrails, health probes, and synthetic canaries."""
import sys
import os

# Ensure local source directory is on Python path
sys.path.insert(0, os.path.abspath("."))

from tests.test_phi_masking import (
    test_phi_masking_identifiers,
    test_telemetry_scrubber_dictionary,
    test_logger_filter_prevents_leaks
)
from tests.test_data_integrity import (
    test_saga_happy_path_commits_all_tiers,
    test_saga_compensates_on_db2_timeout,
    test_idempotency_prevents_duplicate_race_condition,
    test_environment
)
from tests.test_async_workflow import (
    test_async_gateway_returns_http_202_and_polls,
    test_prior_auth_agent_enforces_step_therapy,
    test_root_orchestrator_end_to_end_sanitization_and_commit
)
from tests.test_deepeval_guardrails import (
    test_hipaa_phi_guardrail_zero_leakage,
    test_hipaa_phi_guardrail_catches_leak,
    test_clinical_faithfulness_metric,
    test_async_workflow_sla_metric
)
from tests.test_telemetry_metrics import (
    test_metrics_counter_and_gauge,
    test_histogram_percentiles,
    test_prometheus_text_export
)
from tests.test_component_health import (
    test_component_health_all_healthy,
    test_component_health_degrades_on_db2_timeout
)
from tests.test_alerts import (
    test_alert_fires_on_phi_leak,
    test_alert_fires_on_saga_abort_spike,
    test_alert_fires_on_latency_breach
)
from tests.test_synthetic_canary import (
    test_synthetic_canary_runner_batch
)

def run_all_tests():
    print("======================================================================")
    print("  RUNNING HEALTHCARE AGENT, DEEPEVAL, AND OPERATIONS TELEMETRY SUITE")
    print("======================================================================")
    
    passed = 0
    failed = 0

    tests = [
        # Security & PHI Masking
        ("test_phi_masking_identifiers", lambda: test_phi_masking_identifiers()),
        ("test_telemetry_scrubber_dictionary", lambda: test_telemetry_scrubber_dictionary()),
        ("test_logger_filter_prevents_leaks", lambda: test_logger_filter_prevents_leaks()),
        
        # Multi-Store Data Integrity (Saga, Mongo, Postgres, DB2)
        ("test_saga_happy_path_commits_all_tiers", lambda: test_saga_happy_path_commits_all_tiers(test_environment())),
        ("test_saga_compensates_on_db2_timeout", lambda: test_saga_compensates_on_db2_timeout(test_environment())),
        ("test_idempotency_prevents_duplicate_race_condition", lambda: test_idempotency_prevents_duplicate_race_condition(test_environment())),
        
        # Asynchronous Pharmacy & Prescriber Workflows
        ("test_async_gateway_returns_http_202_and_polls", lambda: test_async_gateway_returns_http_202_and_polls()),
        ("test_prior_auth_agent_enforces_step_therapy", lambda: test_prior_auth_agent_enforces_step_therapy()),
        ("test_root_orchestrator_end_to_end_sanitization_and_commit", lambda: test_root_orchestrator_end_to_end_sanitization_and_commit()),
        
        # DeepEval Guardrails & Validations
        ("test_hipaa_phi_guardrail_zero_leakage", lambda: test_hipaa_phi_guardrail_zero_leakage()),
        ("test_hipaa_phi_guardrail_catches_leak", lambda: test_hipaa_phi_guardrail_catches_leak()),
        ("test_clinical_faithfulness_metric", lambda: test_clinical_faithfulness_metric()),
        ("test_async_workflow_sla_metric", lambda: test_async_workflow_sla_metric()),

        # Telemetry, Prometheus & Performance Metrics
        ("test_metrics_counter_and_gauge", lambda: test_metrics_counter_and_gauge()),
        ("test_histogram_percentiles", lambda: test_histogram_percentiles()),
        ("test_prometheus_text_export", lambda: test_prometheus_text_export()),

        # Component Health Probes
        ("test_component_health_all_healthy", lambda: test_component_health_all_healthy()),
        ("test_component_health_degrades_on_db2_timeout", lambda: test_component_health_degrades_on_db2_timeout()),

        # Operational Alerting Engine
        ("test_alert_fires_on_phi_leak", lambda: test_alert_fires_on_phi_leak()),
        ("test_alert_fires_on_saga_abort_spike", lambda: test_alert_fires_on_saga_abort_spike()),
        ("test_alert_fires_on_latency_breach", lambda: test_alert_fires_on_latency_breach()),

        # Synthetic Canary Runner
        ("test_synthetic_canary_runner_batch", lambda: test_synthetic_canary_runner_batch())
    ]

    for name, fn in tests:
        try:
            fn()
            print(f"  [PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            failed += 1

    print("======================================================================")
    print(f"RESULTS: {passed} PASSED, {failed} FAILED")
    print("======================================================================")
    
    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_all_tests()
