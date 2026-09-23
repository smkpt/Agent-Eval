"""Prometheus / OpenMetrics text exporter for Healthcare Multi-Agent AI."""
from typing import Dict, Any
from src.telemetry.metrics import PerformanceMetricsRegistry, metrics_registry

class PrometheusExporter:
    """Formats metrics in Prometheus / OpenMetrics text exposition format."""
    
    METRIC_HELP = {
        "agent_requests_total": "Total number of clinical agent requests processed",
        "agent_latency_ms": "Agent end-to-end execution latency in milliseconds",
        "saga_transactions_total": "Total cross-store Saga transactions across MongoDB, Postgres, and DB2",
        "phi_redaction_total": "Total number of PHI identifiers detected and sanitized",
        "db_query_duration_ms": "Database query duration across storage tiers",
        "async_pbm_polls_total": "Total HTTP 202 async polling cycles completed",
        "component_health_status": "Health status of each component (1=Healthy, 0=Unhealthy)"
    }

    METRIC_TYPES = {
        "agent_requests_total": "counter",
        "agent_latency_ms": "summary",
        "saga_transactions_total": "counter",
        "phi_redaction_total": "counter",
        "db_query_duration_ms": "summary",
        "async_pbm_polls_total": "counter",
        "component_health_status": "gauge"
    }

    def __init__(self, registry: PerformanceMetricsRegistry = None):
        self.registry = registry or metrics_registry

    def export_text(self) -> str:
        """Generates Prometheus standard text format."""
        snapshot = self.registry.get_all_metrics()
        lines = []

        # Export Counters
        for key, value in sorted(snapshot["counters"].items()):
            base_name = key.split("{")[0]
            help_str = self.METRIC_HELP.get(base_name, f"Counter metric {base_name}")
            metric_type = self.METRIC_TYPES.get(base_name, "counter")
            
            lines.append(f"# HELP {base_name} {help_str}")
            lines.append(f"# TYPE {base_name} {metric_type}")
            lines.append(f"{key} {value}")

        # Export Gauges
        for key, value in sorted(snapshot["gauges"].items()):
            base_name = key.split("{")[0]
            help_str = self.METRIC_HELP.get(base_name, f"Gauge metric {base_name}")
            metric_type = self.METRIC_TYPES.get(base_name, "gauge")
            
            lines.append(f"# HELP {base_name} {help_str}")
            lines.append(f"# TYPE {base_name} {metric_type}")
            lines.append(f"{key} {value}")

        # Export Histograms / Summaries
        for key, stats in sorted(snapshot["histograms"].items()):
            base_name = key.split("{")[0]
            help_str = self.METRIC_HELP.get(base_name, f"Summary metric {base_name}")
            
            lines.append(f"# HELP {base_name} {help_str}")
            lines.append(f"# TYPE {base_name} summary")
            
            lines.append(f'{base_name}{{quantile="0.5"}} {stats["p50"]}')
            lines.append(f'{base_name}{{quantile="0.9"}} {stats["p90"]}')
            lines.append(f'{base_name}{{quantile="0.95"}} {stats["p95"]}')
            lines.append(f'{base_name}{{quantile="0.99"}} {stats["p99"]}')
            lines.append(f'{base_name}_count {stats["count"]}')
            lines.append(f'{base_name}_sum {round(stats["mean"] * stats["count"], 2)}')

        return "\n".join(lines) + "\n"
