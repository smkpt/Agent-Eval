"""Unit tests for performance telemetry and Prometheus exporter."""
from src.telemetry.metrics import PerformanceMetricsRegistry
from src.telemetry.prometheus_exporter import PrometheusExporter

def test_metrics_counter_and_gauge():
    reg = PerformanceMetricsRegistry()
    reg.reset()

    reg.increment_counter("agent_requests_total", 5.0, {"agent": "prescriber"})
    reg.set_gauge("component_health_status", 1.0, {"component": "postgres"})

    assert reg.get_counter_value("agent_requests_total", {"agent": "prescriber"}) == 5.0
    assert reg.get_gauge_value("component_health_status", {"component": "postgres"}) == 1.0

def test_histogram_percentiles():
    reg = PerformanceMetricsRegistry()
    reg.reset()

    # Record 100 latency data points: 1ms to 100ms
    for latency in range(1, 101):
        reg.record_histogram("agent_latency_ms", float(latency))

    percentiles = reg.get_percentiles("agent_latency_ms")
    assert percentiles["count"] == 100
    assert percentiles["min"] == 1.0
    assert percentiles["max"] == 100.0
    assert percentiles["p50"] == 50.0
    assert percentiles["p90"] == 90.0
    assert percentiles["p95"] == 95.0
    assert percentiles["p99"] == 99.0

def test_prometheus_text_export():
    reg = PerformanceMetricsRegistry()
    reg.reset()

    reg.increment_counter("agent_requests_total", 10.0, {"status": "ok"})
    reg.set_gauge("component_health_status", 1.0, {"component": "root"})
    reg.record_histogram("agent_latency_ms", 25.0)

    exporter = PrometheusExporter(registry=reg)
    output = exporter.export_text()

    assert "# HELP agent_requests_total" in output
    assert "# TYPE agent_requests_total counter" in output
    assert 'agent_requests_total{status="ok"} 10.0' in output
    assert 'component_health_status{component="root"} 1.0' in output
    assert 'agent_latency_ms{quantile="0.95"}' in output
