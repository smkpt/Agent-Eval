try:
    import pytest
except ImportError:
    pytest = None
from src.mcp_servers.async_gateway_mcp import AsyncPayerGatewayMCP
from src.agents.prior_auth_agent import PriorAuthAgent
from src.agents.prescriber_agent import PrescriberAgent
from src.agents.root_orchestrator import RootHealthcareOrchestrator
from src.security.phi_masking import PHIMaskingService
from src.storage.mongo_client import MongoClient
from src.storage.postgres_client import PostgresClient
from src.storage.db2_client import DB2Client
from src.saga.saga_coordinator import SagaCoordinator

def test_async_gateway_returns_http_202_and_polls():
    gateway = AsyncPayerGatewayMCP()
    
    # 1. Initial submission returns HTTP 202 Accepted with Retry-After header
    submission = gateway.submit_prior_authorization({"patient": "P-101", "drug": "Ozempic"})
    assert submission["http_status"] == 202
    assert "Location" in submission["headers"]
    assert submission["headers"]["Retry-After"] == "2"
    
    tx_id = submission["transaction_id"]

    # 2. First poll returns IN_REVIEW
    poll_1 = gateway.poll_status(tx_id)
    assert poll_1["status"] == "IN_REVIEW"

    # 3. Second poll returns terminal ADJUDICATED_APPROVED
    poll_2 = gateway.poll_status(tx_id)
    assert poll_2["status"] == "ADJUDICATED_APPROVED"
    assert poll_2["decision"]["covered"] is True

def test_prior_auth_agent_enforces_step_therapy():
    gateway = AsyncPayerGatewayMCP()
    agent = PriorAuthAgent(gateway_mcp=gateway)

    # Inadequate clinical history (no Metformin trial)
    invalid_req = {
        "drug_name": "Ozempic 2mg/3mL",
        "clinical_history": "Patient diagnosed with Type 2 Diabetes yesterday. Wants weight loss."
    }
    result = agent.process_prior_authorization(invalid_req)
    assert result["approved"] is False
    assert "Step therapy requirement unmet" in result["reason"]

    # Adequate clinical history (Type 2 Diabetes + documented Metformin)
    valid_req = {
        "drug_name": "Ozempic 2mg/3mL",
        "clinical_history": "Type 2 Diabetes (E11.9) with suboptimal control on Metformin 1000mg BID for 6 months."
    }
    valid_result = agent.process_prior_authorization(valid_req)
    assert valid_result["approved"] is True
    assert "APPR-GLP1-" in valid_result["approval_code"]

def test_root_orchestrator_end_to_end_sanitization_and_commit():
    gateway = AsyncPayerGatewayMCP()
    pa_agent = PriorAuthAgent(gateway_mcp=gateway)
    prescriber_agent = PrescriberAgent()
    mongo = MongoClient()
    postgres = PostgresClient()
    db2 = DB2Client()
    saga = SagaCoordinator(mongo=mongo, postgres=postgres, db2=db2)
    phi_masker = PHIMaskingService()

    orchestrator = RootHealthcareOrchestrator(
        prescriber_agent=prescriber_agent,
        prior_auth_agent=pa_agent,
        saga_coordinator=saga,
        phi_masker=phi_masker
    )

    request = {
        "order_id": "ORD-E2E-500",
        "idempotency_key": "IDEMP-E2E-500",
        "patient_name": "Robert Davis",
        "ndc_code": "00169-4132-12",  # Ozempic
        "sig": "0.5mg injected subcutaneously once weekly",
        "clinical_notes": (
            "Patient Robert Davis (SSN: 333-22-1111) has Type 2 Diabetes mellitus. "
            "Patient previously completed 180 days on Metformin 1000mg daily."
        )
    }

    response = orchestrator.handle_clinical_request(request)

    assert response["success"] is True
    assert response["order_status"] == "COMMITTED"
    # Verify zero PHI in final summary
    assert "Robert Davis" not in response["sanitized_summary"]
    assert "333-22-1111" not in response["sanitized_summary"]
    assert "<PATIENT_" in response["sanitized_summary"]
