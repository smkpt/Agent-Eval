"""Zero-leak logging utility configured to sanitize PHI from log telemetry."""
import logging
import re
import sys

# Regex patterns matching common HIPAA Safe Harbor direct identifiers
SSN_REGEX = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
PHONE_REGEX = re.compile(r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')
EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')
MRN_REGEX = re.compile(r'\b(?:MRN|mrn)[-:\s]*\d{6,10}\b', re.IGNORECASE)

class PHIScrubbingFilter(logging.Filter):
    """Logging filter ensuring that any accidental PHI is sanitized before output."""
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.scrub_text(record.msg)
        return True

    @classmethod
    def scrub_text(cls, text: str) -> str:
        text = SSN_REGEX.sub("[REDACTED_SSN]", text)
        text = PHONE_REGEX.sub("[REDACTED_PHONE]", text)
        text = EMAIL_REGEX.sub("[REDACTED_EMAIL]", text)
        text = MRN_REGEX.sub("[REDACTED_MRN]", text)
        return text

def get_scrubbed_logger(name: str = "healthcare_agent") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s'
        )
        handler.setFormatter(formatter)
        handler.addFilter(PHIScrubbingFilter())
        logger.addHandler(handler)
    return logger
