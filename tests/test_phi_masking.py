try:
    import pytest
except ImportError:
    pytest = None
from src.security.phi_masking import PHIMaskingService, PHITokenVault
from src.security.telemetry_scrubber import TelemetryScrubber
from src.core.logger import PHIScrubbingFilter

def test_phi_masking_identifiers():
    vault = PHITokenVault()
    service = PHIMaskingService(vault=vault)

    raw_clinical_text = (
        "Patient John Doe (DOB: 04/12/1980, SSN: 123-45-6789, MRN: 9876543) "
        "contacted via phone 555-123-4567 and email jdoe@example.com living at 90210. "
        "Complains of elevated glucose."
    )

    masked_text, session_tokens = service.mask(raw_clinical_text)

    # 1. Assert all direct identifiers are replaced
    assert "John Doe" not in masked_text
    assert "123-45-6789" not in masked_text
    assert "9876543" not in masked_text
    assert "555-123-4567" not in masked_text
    assert "jdoe@example.com" not in masked_text
    assert "04/12/1980" not in masked_text

    # 2. Assert cryptographic tokens are injected
    assert "<SSN_" in masked_text
    assert "<MRN_" in masked_text
    assert "<DOB_" in masked_text

    # 3. Assert reversibility for authorized systems
    rehydrated = service.rehydrate(masked_text, session_tokens)
    assert "123-45-6789" in rehydrated
    assert "John Doe" in rehydrated

def test_telemetry_scrubber_dictionary():
    raw_payload = {
        "event": "prescription_submitted",
        "ssn": "123-45-6789",
        "patient_name": "Alice Smith",
        "nested": {
            "mrn": "11223344",
            "clinical_summary": "Contact patient at 415-555-0199"
        }
    }

    sanitized = TelemetryScrubber.sanitize_dictionary(raw_payload)

    assert sanitized["ssn"] == "[REDACTED_TELEMETRY_PHI]"
    assert sanitized["patient_name"] == "[REDACTED_TELEMETRY_PHI]"
    assert sanitized["nested"]["mrn"] == "[REDACTED_TELEMETRY_PHI]"
    assert "415-555-0199" not in sanitized["nested"]["clinical_summary"]
    assert "[REDACTED_PHONE]" in sanitized["nested"]["clinical_summary"]

def test_logger_filter_prevents_leaks():
    dirty_log = "Processing failure for SSN 999-88-7777 and email test@healthcorp.org"
    scrubbed = PHIScrubbingFilter.scrub_text(dirty_log)
    assert "999-88-7777" not in scrubbed
    assert "test@healthcorp.org" not in scrubbed
    assert "[REDACTED_SSN]" in scrubbed
    assert "[REDACTED_EMAIL]" in scrubbed
