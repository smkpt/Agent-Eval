"""PostgreSQL Client managing operational order states and idempotency locks."""
from typing import Dict, Any, Optional
import time
import copy
import threading

class PostgresClient:
    """Enterprise relational client handling ACID order state and distributed locks."""
    def __init__(self):
        self._orders: Dict[str, Dict[str, Any]] = {}
        self._idempotency_locks: Dict[str, float] = {}  # key -> timestamp
        self._outbox: list = []
        self._lock = threading.Lock()

    def acquire_idempotency_lock(self, idempotency_key: str, ttl_seconds: int = 30) -> bool:
        """Acquires an atomic distributed lock for the transaction."""
        with self._lock:
            now = time.time()
            if idempotency_key in self._idempotency_locks:
                acquired_at = self._idempotency_locks[idempotency_key]
                if now - acquired_at < ttl_seconds:
                    return False  # Lock actively held
            self._idempotency_locks[idempotency_key] = now
            return True

    def release_idempotency_lock(self, idempotency_key: str):
        with self._lock:
            if idempotency_key in self._idempotency_locks:
                del self._idempotency_locks[idempotency_key]

    def create_order(self, order_id: str, idempotency_key: str, details: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            record = {
                "order_id": order_id,
                "idempotency_key": idempotency_key,
                "status": "DRAFT",
                "created_at": time.time(),
                "details": details
            }
            self._orders[order_id] = record
            return record

    def transition_state(self, order_id: str, new_status: str) -> bool:
        with self._lock:
            if order_id in self._orders:
                self._orders[order_id]["status"] = new_status
                self._outbox.append({
                    "event": "ORDER_STATUS_CHANGED",
                    "order_id": order_id,
                    "status": new_status,
                    "timestamp": time.time()
                })
                return True
            return False

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            order = self._orders.get(order_id)
            return copy.deepcopy(order) if order else None

    def clear(self):
        with self._lock:
            self._orders.clear()
            self._idempotency_locks.clear()
            self._outbox.clear()
