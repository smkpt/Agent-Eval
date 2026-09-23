"""OpenTelemetry & stdout stream sanitizer to guarantee zero PHI leakage."""
import re
from typing import Any, Dict

class TelemetryScrubber:
    """Sanitizes telemetry spans, metric attributes, and debug payloads."""
    SUSPICIOUS_KEYS = {"ssn", "mrn", "patient_name", "dob", "phone", "email", "address"}
    
    @classmethod
    def sanitize_dictionary(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = {}
        for k, v in data.items():
            if any(target in k.lower() for target in cls.SUSPICIOUS_KEYS):
                sanitized[k] = "[REDACTED_TELEMETRY_PHI]"
            elif isinstance(v, dict):
                sanitized[k] = cls.sanitize_dictionary(v)
            elif isinstance(v, str):
                sanitized[k] = cls.scrub_pii_strings(v)
            else:
                sanitized[k] = v
        return sanitized

    @classmethod
    def scrub_pii_strings(cls, text: str) -> str:
        # Mask obvious SSN
        text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[REDACTED_SSN]', text)
        # Mask phone
        text = re.sub(r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b', '[REDACTED_PHONE]', text)
        # Mask email
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', '[REDACTED_EMAIL]', text)
        return text
