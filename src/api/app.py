"""FastAPI HTTP Application exposing Healthcare Multi-Agent API for Locust and JMeter."""
from fastapi import FastAPI, Response, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

from src.agents.root_orchestrator import RootHealthcareOrchestrator
from src.agents.prescriber_agent import PrescriberAgent
from src.agents.prior_auth_agent import PriorAuthAgent
from src.saga.saga_coordinator import SagaCoordinator
from src.mcp_servers.async_gateway_mcp import AsyncPayerGatewayMCP
from src.security.phi_masking import PHIMaskingService
from src.storage.mongo_client import MongoClient
from src.storage.postgres_client import PostgresClient
from src.storage.db2_client import DB2Client
from src.telemetry.health import ComponentHealthCheck
from src.telemetry.prometheus_exporter import PrometheusExporter
from src.telemetry.synthetic_runner import SyntheticCanaryRunner

# Instantiate singleton runtime components
gateway = AsyncPayerGatewayMCP()
mongo = MongoClient()
postgres = PostgresClient()
db2 = DB2Client()
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

health_checker = ComponentHealthCheck(mongo=mongo, postgres=postgres, db2=db2, gateway=gateway)
prom_exporter = PrometheusExporter()
canary_runner = SyntheticCanaryRunner()

app = FastAPI(
    title="Healthcare AI Multi-Agent API",
    description="Production-grade API for Asynchronous Pharmacy & Prior Auth Workflows",
    version="1.0.0"
)

class PrescriptionRequest(BaseModel):
    order_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    patient_name: str = "Anonymous Patient"
    ndc_code: str = "00169-4132-12"
    sig: str = "Take as directed"
    clinical_notes: str = ""

@app.post("/api/v1/prescriptions", status_code=status.HTTP_200_OK)
def submit_prescription(req: PrescriptionRequest, response: Response):
    """Processes an e-prescription order with HIPAA de-identification and async prior auth."""
    payload = req.model_dump()
    result = orchestrator.handle_clinical_request(payload)
    if not result.get("success"):
        response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    return result

@app.get("/api/v1/prior-auth/{tx_id}/status")
def get_prior_auth_status(tx_id: str):
    """Asynchronous polling endpoint conforming to RFC 7231 HTTP 202 Accepted."""
    return gateway.poll_status(tx_id)

@app.get("/health")
def get_health():
    """Component readiness and liveness diagnostic probes."""
    return health_checker.check_all()

@app.get("/metrics")
def get_metrics():
    """Prometheus / OpenMetrics exposition format endpoint."""
    text_content = prom_exporter.export_text()
    return Response(content=text_content, media_type="text/plain; version=0.0.4")

@app.post("/api/v1/canary/run")
def trigger_canary_batch(count: int = 4):
    """Executes a round of synthetic clinical traffic for SLA benchmarking."""
    return canary_runner.run_canary_batch(count=count)
