"""IBM DB2 Mainframe Client for PBM Core Claims and Financial Balances."""
from typing import Dict, Any, Optional

class DB2Client:
    """Core PBM billing mainframe ledger client with fault-injection support."""
    def __init__(self):
        self._ledger: Dict[str, Dict[str, Any]] = {}
        self.simulate_timeout: bool = False
        self.simulate_reject: bool = False

    def post_claim(self, claim_id: str, order_id: str, amount: float, drug_ndc: str) -> Dict[str, Any]:
        if self.simulate_timeout:
            raise TimeoutError("DB2 Mainframe Gateway Timed Out (DRDA Protocol Timeout)")
        if self.simulate_reject:
            raise ValueError("DB2 Core Rejected Claim: Member Benefit Exhausted")

        entry = {
            "claim_id": claim_id,
            "order_id": order_id,
            "amount": amount,
            "drug_ndc": drug_ndc,
            "status": "ADJUDICATED_COMMITTED"
        }
        self._ledger[claim_id] = entry
        return entry

    def void_claim(self, claim_id: str) -> bool:
        """Compensating transaction to reverse an adjudicated claim on the mainframe."""
        if claim_id in self._ledger:
            self._ledger[claim_id]["status"] = "VOIDED_REVERSED"
            return True
        return False

    def get_claim(self, claim_id: str) -> Optional[Dict[str, Any]]:
        return self._ledger.get(claim_id)

    def clear(self):
        self._ledger.clear()
        self.simulate_timeout = False
        self.simulate_reject = False
