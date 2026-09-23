"""Prior Authorization Specialist Agent coordinating async payer adjudication."""
from typing import Dict, Any
from src.mcp_servers.async_gateway_mcp import AsyncPayerGatewayMCP
from src.core.logger import get_scrubbed_logger

logger = get_scrubbed_logger("prior_auth_agent")

class PriorAuthAgent:
    """Specialist agent for evaluating clinical criteria and managing async PA workflows."""
    def __init__(self, gateway_mcp: AsyncPayerGatewayMCP):
        self.gateway = gateway_mcp

    def process_prior_authorization(self, pa_request: Dict[str, Any]) -> Dict[str, Any]:
        """Validates clinical step-therapy criteria and runs async adjudication."""
        clinical_history = pa_request.get("clinical_history", "").lower()
        drug_name = pa_request.get("drug_name", "").lower()

        # Step Therapy Clinical Guideline Check
        has_diabetes = "type 2 diabetes" in clinical_history or "e11" in clinical_history
        has_metformin_trial = "metformin" in clinical_history

        if ("ozempic" in drug_name or "trulicity" in drug_name) and not (has_diabetes and has_metformin_trial):
            logger.warning("Clinical criteria not met: Prior step therapy with Metformin required.")
            return {
                "approved": False,
                "reason": "Step therapy requirement unmet: Documented trial of first-line Metformin required for GLP-1 coverage under CMS-0057-F guidelines.",
                "async_transaction_id": None
            }

        # Step 1: Submit to async PBM gateway
        submission = self.gateway.submit_prior_authorization(pa_request)
        tx_id = submission["transaction_id"]
        logger.info(f"Prior Authorization submitted: HTTP 202 Accepted. Transaction ID: {tx_id}")

        # Step 2: Asynchronous Polling loop
        max_attempts = 3
        for attempt in range(max_attempts):
            poll_res = self.gateway.poll_status(tx_id)
            if poll_res.get("status") == "ADJUDICATED_APPROVED":
                logger.info(f"Prior Auth {tx_id} successfully adjudicated.")
                return {
                    "approved": True,
                    "transaction_id": tx_id,
                    "approval_code": poll_res["decision"]["approval_code"],
                    "copay_amount": poll_res["decision"]["copay_amount"],
                    "guideline_met": poll_res["decision"]["guideline_met"]
                }
            logger.info(f"PA {tx_id} status: {poll_res.get('status')}. Polling again...")

        return {
            "approved": False,
            "reason": "Prior authorization adjudication timed out.",
            "transaction_id": tx_id
        }
