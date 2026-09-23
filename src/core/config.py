"""Core settings and configuration for the healthcare multi-agent architecture."""
import os
from dataclasses import dataclass, field

@dataclass
class Settings:
    environment: str = os.getenv("ENV", "test")
    service_name: str = "healthcare-agent-poc"
    
    # Asynchronous Gateway Configuration
    async_retry_after_seconds: int = 2
    async_max_retries: int = 5
    async_timeout_seconds: int = 15
    
    # HIPAA & PHI Masking
    enable_strict_phi_masking: bool = True
    phi_token_salt: str = os.getenv("PHI_SALT", "enterprise-hipaa-salt-99214")
    
    # Multi-Tier Storage Settings
    postgres_url: str = os.getenv("POSTGRES_URL", "postgresql://user:pass@localhost:5432/healthcare_ops")
    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://localhost:27017/clinical_fhir")
    db2_connection_string: str = os.getenv("DB2_CONN", "DATABASE=CORECLM;HOSTNAME=db2main.health;PORT=50000;")
    
    # DeepEval Evaluator Settings
    deepeval_model: str = os.getenv("DEEPEVAL_MODEL", "gpt-4o")
    faithfulness_threshold: float = 0.90
    phi_leakage_threshold: float = 1.0  # Zero tolerance (1.0 = pass, any leak fails)

settings = Settings()
