"""IBM DB2 Mainframe Client for PBM Core Claims and Financial Balances."""
from typing import Dict, Any, Optional
import copy
import threading

class DB2Client:
    """Core PBM billing mainframe ledger client with fault-injection support."""
    def __init__(self):
        self._ledger: Dict[str, Dict[str, Any]] = {}
        self.simulate_timeout: bool = False
        self.simulate_reject: bool = False
        self._lock = threading.Lock()

    def post_claim(self, claim_id: str, order_id: str, amount: float, drug_ndc: str) -> Dict[str, Any]:
        with self._lock:
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
        with self._lock:
            if claim_id in self._ledger:
                self._ledger[claim_id]["status"] = "VOIDED_REVERSED"
                return True
            return False

    def get_claim(self, claim_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            claim = self._ledger.get(claim_id)
            return copy.deepcopy(claim) if claim else None

    def clear(self):
        with self._lock:
            self._ledger.clear()
            self.simulate_timeout = False
            self.simulate_reject = False
