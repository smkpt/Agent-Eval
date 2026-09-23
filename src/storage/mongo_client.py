"""MongoDB Client for unstructured clinical documents and FHIR bundles."""
from typing import Dict, Any, Optional
import copy
import threading

class MongoClient:
    """In-memory and enterprise-ready adapter for MongoDB FHIR storage."""
    def __init__(self):
        self._collections: Dict[str, Dict[str, Any]] = {
            "clinical_notes": {},
            "fhir_bundles": {},
            "audit_logs": {}
        }
        self._lock = threading.Lock()

    def insert_fhir_bundle(self, bundle_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            doc = copy.deepcopy(payload)
            doc["_id"] = bundle_id
            doc["workflow_status"] = doc.get("workflow_status", "ACTIVE")
            self._collections["fhir_bundles"][bundle_id] = doc
            return doc

    def get_bundle(self, bundle_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            doc = self._collections["fhir_bundles"].get(bundle_id)
            return copy.deepcopy(doc) if doc else None

    def update_bundle_status(self, bundle_id: str, new_status: str) -> bool:
        with self._lock:
            if bundle_id in self._collections["fhir_bundles"]:
                self._collections["fhir_bundles"][bundle_id]["workflow_status"] = new_status
                return True
            return False

    def remove_bundle(self, bundle_id: str) -> bool:
        with self._lock:
            if bundle_id in self._collections["fhir_bundles"]:
                del self._collections["fhir_bundles"][bundle_id]
                return True
            return False

    def clear(self):
        with self._lock:
            for col in self._collections.values():
                col.clear()
