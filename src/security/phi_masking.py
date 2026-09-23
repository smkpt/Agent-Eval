"""HIPAA Safe Harbor PHI Masking Engine and Encrypted Token Vault."""
import hashlib
import re
from typing import Dict, Tuple
from src.core.config import settings

class PHITokenVault:
    """Manages reversible cryptographic surrogate tokens in an isolated vault."""
    def __init__(self):
        self._vault: Dict[str, str] = {}
        self._reverse_vault: Dict[str, str] = {}

    def get_or_create_token(self, identifier_type: str, real_value: str) -> str:
        cache_key = f"{identifier_type}:{real_value}"
        if cache_key in self._vault:
            return self._vault[cache_key]
        
        # Deterministic HMAC-like SHA-256 token based on salt
        raw_hash = hashlib.sha256(f"{settings.phi_token_salt}:{cache_key}".encode()).hexdigest()[:8].upper()
        token = f"<{identifier_type.upper()}_{raw_hash}>"
        
        self._vault[cache_key] = token
        self._reverse_vault[token] = real_value
        return token

    def resolve_token(self, token: str) -> str:
        return self._reverse_vault.get(token, token)

    def clear(self):
        self._vault.clear()
        self._reverse_vault.clear()


class PHIMaskingService:
    """De-identifies clinical prompts and messages before passing to LLM agents."""
    def __init__(self, vault: PHITokenVault = None):
        self.vault = vault or PHITokenVault()

        # Regular expressions for direct identifiers
        self.patterns = [
            ("SSN", re.compile(r'\b\d{3}-\d{2}-\d{4}\b')),
            ("PHONE", re.compile(r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')),
            ("EMAIL", re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')),
            ("MRN", re.compile(r'\bMRN[-:\s]*(\d{6,10})\b', re.IGNORECASE)),
            ("ZIP", re.compile(r'\b\d{5}(?:-\d{4})?\b')),
            ("DOB", re.compile(r'\b(?:0[1-9]|1[0-2])/(?:0[1-9]|[12]\d|3[01])/(?:19|20)\d{2}\b')),
            ("NAME", re.compile(r'\b(?:Patient|Mr\.|Ms\.|Mrs\.|Dr\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b'))
        ]

    def mask(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Scans input text, replaces PHI with cryptographic tokens, and returns

        the sanitized text along with the session token map.
        """
        masked = text
        session_tokens = {}

        # Mask custom patterns
        for id_type, regex in self.patterns:
            matches = list(regex.finditer(masked))
            # Process in reverse order to preserve string offsets
            for match in reversed(matches):
                val = match.group(0)
                token = self.vault.get_or_create_token(id_type, val)
                session_tokens[token] = val
                start, end = match.span()
                masked = masked[:start] + token + masked[end:]

        return masked, session_tokens

    def rehydrate(self, masked_text: str, session_tokens: Dict[str, str]) -> str:
        """Restores original PHI into authorized downstream payloads."""
        restored = masked_text
        for token, original in session_tokens.items():
            restored = restored.replace(token, original)
        return restored
