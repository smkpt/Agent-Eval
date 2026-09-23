"""Unit tests for the operational alerting rules engine."""
from src.telemetry.alerts import AlertManager, AlertSeverity

def test_alert_fires_on_phi_leak():
    manager = AlertManager()
    manager.clear()

    snapshot = {
        "counters": {
            "phi_leak_events_total": 1.0
        },
        "histograms": {}
    }

    active_alerts = manager.evaluate_rules(snapshot)
    assert len(active_alerts) == 1
    assert active_alerts[0]["severity"] == AlertSeverity.P0_CRITICAL
    assert active_alerts[0]["rule_id"] == "RULE_PHI_LEAK_DETECTED"

def test_alert_fires_on_saga_abort_spike():
    manager = AlertManager()
    manager.clear()

    # 10 committed, 5 compensated = 33% abort rate (threshold is 10%)
    snapshot = {
        "counters": {
            'saga_transactions_total{status="committed"}': 10.0,
            'saga_transactions_total{status="compensated"}': 5.0
        },
        "histograms": {}
    }

    active_alerts = manager.evaluate_rules(snapshot)
    assert any(a["rule_id"] == "RULE_SAGA_ABORT_SPIKE" for a in active_alerts)

def test_alert_fires_on_latency_breach():
    manager = AlertManager()
    manager.clear()

    snapshot = {
        "counters": {},
        "histograms": {
            "agent_latency_ms": {"p95": 3200.0}  # threshold is 2500ms
        }
    }

    active_alerts = manager.evaluate_rules(snapshot)
    assert any(a["rule_id"] == "RULE_LATENCY_P95_BREACH" for a in active_alerts)
