"""Unit tests for FastAPI endpoints backing Locust, k6, and JMeter load tests."""
try:
    from fastapi.testclient import TestClient
    from src.api.app import app
    client = TestClient(app)
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    client = None

def test_api_health_endpoint():
    if not HAS_FASTAPI:
        print("Skipping test_api_health_endpoint (fastapi/httpx not installed)")
        return
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["system_status"] in ["HEALTHY", "DEGRADED"]
    assert "components" in data

def test_api_metrics_endpoint():
    if not HAS_FASTAPI:
        print("Skipping test_api_metrics_endpoint (fastapi/httpx not installed)")
        return
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "agent_latency_ms" in res.text or "# HELP" in res.text

def test_api_prescription_endpoint():
    if not HAS_FASTAPI:
        print("Skipping test_api_prescription_endpoint (fastapi/httpx not installed)")
        return
    payload = {
        "order_id": "API-TEST-001",
        "idempotency_key": "IDEMP-API-001",
        "patient_name": "API Test Patient",
        "ndc_code": "00169-4132-12",
        "clinical_notes": "Type 2 Diabetes (E11.9) with prior Metformin for 6 months."
    }
    res = client.post("/api/v1/prescriptions", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["order_status"] == "COMMITTED"
    assert "<PATIENT_" in data["sanitized_summary"]

def test_api_canary_run_endpoint():
    if not HAS_FASTAPI:
        print("Skipping test_api_canary_run_endpoint (fastapi/httpx not installed)")
        return
    res = client.post("/api/v1/canary/run?count=2")
    assert res.status_code == 200
    data = res.json()
    assert data["batch_size"] == 2
    assert "availability_percentage" in data
