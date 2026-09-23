"""Prescriber Specialist Agent handling e-prescriptions and NCPDP/FHIR schemas."""
from typing import Dict, Any

class PrescriberAgent:
    """Specialist agent responsible for e-prescribing validation and FHIR encoding."""
    
    FORMULARY_DATABASE = {
        "00002-1433-80": {"name": "Trulicity (dulaglutide) 1.5mg/0.5mL", "tier": 2, "requires_pa": True},
        "00169-4132-12": {"name": "Ozempic (semaglutide) 2mg/3mL", "tier": 2, "requires_pa": True},
        "00093-7212-01": {"name": "Metformin HCl 500mg", "tier": 1, "requires_pa": False}
    }

    def validate_and_compose_rx(self, order_request: Dict[str, Any]) -> Dict[str, Any]:
        ndc = order_request.get("ndc_code")
        drug_info = self.FORMULARY_DATABASE.get(ndc)

        if not drug_info:
            return {
                "valid": False,
                "error": f"NDC Code {ndc} not found in national active formulary."
            }

        # Build FHIR R4 MedicationRequest representation
        fhir_med_req = {
            "resourceType": "MedicationRequest",
            "status": "draft",
            "intent": "order",
            "medicationCodeableConcept": {
                "coding": [{
                    "system": "http://hl7.org/fhir/sid/ndc",
                    "code": ndc,
                    "display": drug_info["name"]
                }]
            },
            "subject": {
                "reference": f"Patient/{order_request.get('patient_token')}"
            },
            "dosageInstruction": [{
                "text": order_request.get("sig", "Take as directed")
            }],
            "requires_prior_authorization": drug_info["requires_pa"]
        }

        return {
            "valid": True,
            "drug_info": drug_info,
            "fhir_medication_request": fhir_med_req
        }
