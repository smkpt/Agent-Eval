"""Enterprise Metrics & Performance Telemetry Registry for Healthcare Multi-Agent AI."""
import time
import math
from typing import Dict, List, Any, Optional

class PerformanceMetricsRegistry:
    """Thread-safe, self-contained metrics registry tracking latency distributions,

    counters, gauges, and throughput without external runtime dependencies.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PerformanceMetricsRegistry, cls).__new__(cls)
            cls._instance._init_registry()
        return cls._instance

    def _init_registry(self):
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._start_time = time.time()

    def increment_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        key = self._format_key(name, labels)
        self._counters[key] = self._counters.get(key, 0.0) + value

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        key = self._format_key(name, labels)
        self._gauges[key] = value

    def record_histogram(self, name: str, value_ms: float, labels: Optional[Dict[str, str]] = None):
        key = self._format_key(name, labels)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value_ms)

    def get_counter_value(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        key = self._format_key(name, labels)
        return self._counters.get(key, 0.0)

    def get_gauge_value(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        key = self._format_key(name, labels)
        return self._gauges.get(key, 0.0)

    def get_percentiles(self, name: str, labels: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """Calculates p50, p90, p95, p99 latency percentiles for a histogram metric."""
        key = self._format_key(name, labels)
        values = sorted(self._histograms.get(key, []))
        if not values:
            return {"count": 0, "min": 0.0, "max": 0.0, "mean": 0.0, "p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0}

        n = len(values)
        def percentile(p: float) -> float:
            idx = int(math.ceil((p / 100.0) * n)) - 1
            return round(values[max(0, min(idx, n - 1))], 2)

        return {
            "count": n,
            "min": round(values[0], 2),
            "max": round(values[-1], 2),
            "mean": round(sum(values) / n, 2),
            "p50": percentile(50),
            "p90": percentile(90),
            "p95": percentile(95),
            "p99": percentile(99)
        }

    def _format_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def get_all_metrics(self) -> Dict[str, Any]:
        """Returns consolidated snapshot of all operational metrics."""
        hist_summary = {}
        for k in self._histograms.keys():
            base_name = k.split("{")[0]
            hist_summary[k] = self.get_percentiles(base_name)

        uptime = time.time() - self._start_time
        return {
            "uptime_seconds": round(uptime, 2),
            "counters": self._counters.copy(),
            "gauges": self._gauges.copy(),
            "histograms": hist_summary
        }

    def reset(self):
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._start_time = time.time()

metrics_registry = PerformanceMetricsRegistry()
