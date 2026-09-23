"""Saga Coordinator enforcing data-aware integrity across Mongo, Postgres, and DB2."""
from typing import Dict, Any
from src.storage.mongo_client import MongoClient
from src.storage.postgres_client import PostgresClient
from src.storage.db2_client import DB2Client
from src.core.logger import get_scrubbed_logger

logger = get_scrubbed_logger("saga_coordinator")

class SagaCoordinator:
    """Coordinates multi-tier distributed transactions with automated compensation."""
    def __init__(self, mongo: MongoClient, postgres: PostgresClient, db2: DB2Client):
        self.mongo = mongo
        self.postgres = postgres
        self.db2 = db2

    def execute_prescription_saga(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        order_id = payload["order_id"]
        idempotency_key = payload["idempotency_key"]
        claim_id = f"CLM-{order_id}"
        
        logger.info(f"Initiating Prescription Saga for Order: {order_id} with key: {idempotency_key}")

        # Step 1: Distributed Idempotency Lock
        if not self.postgres.acquire_idempotency_lock(idempotency_key):
            logger.warning(f"Concurrent request detected for key: {idempotency_key}. Rejecting to prevent race condition.")
            return {
                "order_id": order_id,
                "status": "REJECTED_CONCURRENT_TRANSACTION",
                "message": "Duplicate or concurrent transaction actively locked."
            }

        try:
            # Step 2: Postgres Order Creation (DRAFT)
            self.postgres.create_order(order_id, idempotency_key, payload)

            # Step 3: MongoDB Clinical Document Persistence
            fhir_bundle = {
                "resourceType": "Bundle",
                "id": order_id,
                "entry": [{
                    "resource": {
                        "resourceType": "MedicationRequest",
                        "id": order_id,
                        "status": "active",
                        "medicationCodeableConcept": {"text": payload.get("medication_name")},
                        "subject": {"reference": payload.get("patient_token")}
                    }
                }],
                "clinical_notes": payload.get("clinical_justification", "")
            }
            self.mongo.insert_fhir_bundle(order_id, fhir_bundle)

            # Step 4: DB2 Core Claims Adjudication (Mainframe)
            self.db2.post_claim(
                claim_id=claim_id,
                order_id=order_id,
                amount=payload.get("copay_amount", 25.0),
                drug_ndc=payload.get("ndc_code", "00002-1433-80")
            )

            # Step 5: Commit Transaction across operational systems
            self.postgres.transition_state(order_id, "COMMITTED")
            self.mongo.update_bundle_status(order_id, "COMMITTED")
            
            logger.info(f"Saga successfully committed for Order: {order_id}")
            return {
                "order_id": order_id,
                "claim_id": claim_id,
                "status": "SUCCESS_COMMITTED"
            }

        except Exception as exc:
            logger.error(f"Saga failed during step execution: {str(exc)}. Initiating automated compensation.")
            self._compensate(order_id, claim_id)
            return {
                "order_id": order_id,
                "status": "COMPENSATED_FAILED",
                "error": str(exc)
            }
        finally:
            self.postgres.release_idempotency_lock(idempotency_key)

    def _compensate(self, order_id: str, claim_id: str):
        """Rolls back all downstream tier mutations to prevent orphan states."""
        # Compensate DB2
        try:
            self.db2.void_claim(claim_id)
        except Exception as e:
            logger.error(f"Compensating DB2 failed: {e}")

        # Compensate Mongo
        try:
            self.mongo.update_bundle_status(order_id, "ABORTED_ORPHAN_PREVENTED")
        except Exception as e:
            logger.error(f"Compensating Mongo failed: {e}")

        # Compensate Postgres
        try:
            self.postgres.transition_state(order_id, "ROLLED_BACK_SAGA_ABORT")
        except Exception as e:
            logger.error(f"Compensating Postgres failed: {e}")
