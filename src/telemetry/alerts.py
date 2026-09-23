"""Operational Alerting Rules Engine & Notification Dispatcher."""
import time
from typing import Dict, Any, List
from src.telemetry.metrics import metrics_registry
from src.core.logger import get_scrubbed_logger

logger = get_scrubbed_logger("alert_manager")

class AlertSeverity:
    P0_CRITICAL = "P0_CRITICAL"
    P1_HIGH = "P1_HIGH"
    P2_MEDIUM = "P2_MEDIUM"
    P3_INFO = "P3_INFO"

class AlertManager:
    """Evaluates operational telemetry against alert threshold rules."""
    def __init__(self):
        self._alerts_history: List[Dict[str, Any]] = []

    def evaluate_rules(self, metrics_snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Evaluates metrics against active operational alert rules."""
        active_alerts = []
        counters = metrics_snapshot.get("counters", {})
        histograms = metrics_snapshot.get("histograms", {})

        # 1. Rule: PHI Direct Identifier Leak Detected (P0 Critical)
        phi_leaks = counters.get("phi_leak_events_total", 0.0)
        if phi_leaks > 0:
            active_alerts.append(self._create_alert(
                rule_id="RULE_PHI_LEAK_DETECTED",
                severity=AlertSeverity.P0_CRITICAL,
                title="HIPAA Security Violation: Unmasked PHI Detected",
                description=f"Automated guardrails detected {int(phi_leaks)} unmasked PHI leak attempts."
            ))

        # 2. Rule: Saga Compensation / Abort Spike (P1 High)
        saga_committed = counters.get('saga_transactions_total{status="committed"}', 0.0)
        saga_compensated = counters.get('saga_transactions_total{status="compensated"}', 0.0)
        total_saga = saga_committed + saga_compensated
        if total_saga >= 5:
            abort_rate = (saga_compensated / total_saga) * 100.0
            if abort_rate > 10.0:
                active_alerts.append(self._create_alert(
                    rule_id="RULE_SAGA_ABORT_SPIKE",
                    severity=AlertSeverity.P1_HIGH,
                    title="Data Integrity Warning: Elevated Saga Compensation Rate",
                    description=f"Saga abort rate reached {abort_rate:.1f}% ({int(saga_compensated)} of {int(total_saga)} transactions)."
                ))

        # 3. Rule: DB2 Mainframe Timeout (P1 High)
        db2_timeouts = counters.get('db_timeout_total{datastore="db2"}', 0.0)
        if db2_timeouts > 0:
            active_alerts.append(self._create_alert(
                rule_id="RULE_DB2_MAINFRAME_TIMEOUT",
                severity=AlertSeverity.P1_HIGH,
                title="Mainframe Core Latency: IBM DB2 DRDA Timeout",
                description=f"Detected {int(db2_timeouts)} connection timeouts to the DB2 claims mainframe."
            ))

        # 4. Rule: Agent P95 Latency Breach (P2 Medium)
        agent_latency = histograms.get("agent_latency_ms", {})
        p95 = agent_latency.get("p95", 0.0)
        if p95 > 2500.0:
            active_alerts.append(self._create_alert(
                rule_id="RULE_LATENCY_P95_BREACH",
                severity=AlertSeverity.P2_MEDIUM,
                title="SLA Warning: Agent P95 Latency Exceeded",
                description=f"Agent p95 latency is {p95}ms (SLA threshold: 2500ms)."
            ))

        return active_alerts

    def _create_alert(self, rule_id: str, severity: str, title: str, description: str) -> Dict[str, Any]:
        alert = {
            "alert_id": f"ALT-{int(time.time() * 1000)}-{rule_id[:8]}",
            "rule_id": rule_id,
            "severity": severity,
            "title": title,
            "description": description,
            "timestamp": time.time(),
            "status": "FIRING"
        }
        self._alerts_history.append(alert)
        logger.warning(f"ALERT [{severity}] {title}: {description}")
        return alert

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self._alerts_history)

    def clear(self):
        self._alerts_history.clear()

alert_manager = AlertManager()
