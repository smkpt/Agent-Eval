"""Root Supervisor Agent orchestrating specialist agents, security, and multi-tier saga."""
from typing import Dict, Any
from src.security.phi_masking import PHIMaskingService
from src.agents.prescriber_agent import PrescriberAgent
from src.agents.prior_auth_agent import PriorAuthAgent
from src.saga.saga_coordinator import SagaCoordinator
from src.core.logger import get_scrubbed_logger

logger = get_scrubbed_logger("root_orchestrator")

class RootHealthcareOrchestrator:
    """Supervisory agent responsible for workflow planning, HIPAA de-identification,

    and multi-system coordination.
    """
    def __init__(
        self,
        prescriber_agent: PrescriberAgent,
        prior_auth_agent: PriorAuthAgent,
        saga_coordinator: SagaCoordinator,
        phi_masker: PHIMaskingService
    ):
        self.prescriber_agent = prescriber_agent
        self.prior_auth_agent = prior_auth_agent
        self.saga_coordinator = saga_coordinator
        self.phi_masker = phi_masker

    def handle_clinical_request(self, raw_request: Dict[str, Any]) -> Dict[str, Any]:
        """Processes clinical prescription order with end-to-end PHI protection and async saga."""
        # Step 1: Inbound HIPAA PHI Masking
        unmasked_notes = raw_request.get("clinical_notes", "")
        masked_notes, session_tokens = self.phi_masker.mask(unmasked_notes)
        
        patient_token = self.phi_masker.vault.get_or_create_token(
            "PATIENT", raw_request.get("patient_name", "UNKNOWN")
        )

        logger.info(f"Processing order for tokenized subject: {patient_token}")

        # Step 2: Prescriber Specialist Validation
        rx_request = {
            "ndc_code": raw_request.get("ndc_code"),
            "patient_token": patient_token,
            "sig": raw_request.get("sig", "Take as directed")
        }
        rx_validation = self.prescriber_agent.validate_and_compose_rx(rx_request)
        if not rx_validation["valid"]:
            return {
                "success": False,
                "error": rx_validation["error"],
                "sanitized_summary": f"Prescription failed: {rx_validation['error']}"
            }

        # Step 3: Prior Authorization Workflow (if required)
        copay_amount = 15.0
        if rx_validation["drug_info"]["requires_pa"]:
            pa_payload = {
                "drug_name": rx_validation["drug_info"]["name"],
                "patient_token": patient_token,
                "clinical_history": masked_notes
            }
            pa_result = self.prior_auth_agent.process_prior_authorization(pa_payload)
            if not pa_result["approved"]:
                return {
                    "success": False,
                    "order_status": "DENIED_PRIOR_AUTH",
                    "reason": pa_result.get("reason"),
                    "sanitized_summary": (
                        f"Order for {rx_validation['drug_info']['name']} on subject {patient_token} "
                        f"was denied prior authorization. Reason: {pa_result.get('reason')}"
                    )
                }
            copay_amount = pa_result.get("copay_amount", 25.0)

        # Step 4: Multi-Store Saga Coordination across MongoDB, Postgres, and DB2
        order_id = raw_request.get("order_id", f"ORD-{patient_token[-6:]}")
        saga_payload = {
            "order_id": order_id,
            "idempotency_key": raw_request.get("idempotency_key", f"IDEMP-{order_id}"),
            "patient_token": patient_token,
            "medication_name": rx_validation["drug_info"]["name"],
            "ndc_code": raw_request.get("ndc_code"),
            "copay_amount": copay_amount,
            "clinical_justification": masked_notes
        }
        
        saga_result = self.saga_coordinator.execute_prescription_saga(saga_payload)
        
        if saga_result["status"] != "SUCCESS_COMMITTED":
            return {
                "success": False,
                "order_status": "SAGA_EXECUTION_FAILED",
                "error": saga_result.get("error", "Failed cross-store data commit"),
                "sanitized_summary": f"Order {order_id} failed multi-tier synchronization and was compensated."
            }

        # Step 5: Final Sanitized Output Generation (Zero PHI leakage)
        summary = (
            f"Successfully processed E-Prescription {order_id} for {rx_validation['drug_info']['name']}. "
            f"Subject: {patient_token}. Prior Auth: APPROVED. Co-pay: ${copay_amount:.2f}. "
            f"Cross-store synchronization status: COMMITTED across MongoDB, Postgres, and DB2."
        )

        return {
            "success": True,
            "order_id": order_id,
            "order_status": "COMMITTED",
            "patient_token": patient_token,
            "copay_amount": copay_amount,
            "sanitized_summary": summary
        }
