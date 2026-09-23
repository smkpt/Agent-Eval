"""Unit tests for synthetic canary test runner and operational SLA validation."""
from src.telemetry.synthetic_runner import SyntheticCanaryRunner

def test_synthetic_canary_runner_batch():
    runner = SyntheticCanaryRunner()

    report = runner.run_canary_batch(count=4)

    assert report["batch_size"] == 4
    # All 4 synthetic scenarios should execute according to their clinical & resilience specifications
    assert report["passed_count"] == 4
    assert report["failed_count"] == 0
    assert report["availability_percentage"] == 100.0
    assert len(report["scenarios"]) == 4

    # Verify scenario names executed
    scenario_names = [s["scenario"] for s in report["scenarios"]]
    assert any("Happy Path" in s for s in scenario_names)
    assert any("Clinical Rule" in s for s in scenario_names)
    assert any("Resilience" in s for s in scenario_names)
    assert any("Concurrency" in s for s in scenario_names)
