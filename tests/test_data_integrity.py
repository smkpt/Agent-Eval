try:
    import pytest
    fixture_decorator = pytest.fixture
except ImportError:
    pytest = None
    fixture_decorator = lambda f: f

from src.storage.mongo_client import MongoClient
from src.storage.postgres_client import PostgresClient
from src.storage.db2_client import DB2Client
from src.saga.saga_coordinator import SagaCoordinator

@fixture_decorator
def test_environment():
    mongo = MongoClient()
    postgres = PostgresClient()
    db2 = DB2Client()
    coordinator = SagaCoordinator(mongo=mongo, postgres=postgres, db2=db2)
    return {
        "mongo": mongo,
        "postgres": postgres,
        "db2": db2,
        "coordinator": coordinator
    }

def test_saga_happy_path_commits_all_tiers(test_environment):
    env = test_environment
    order_id = "ORD-TEST-1001"
    idempotency_key = "IDEMP-KEY-9901"

    payload = {
        "order_id": order_id,
        "idempotency_key": idempotency_key,
        "patient_token": "<PATIENT_TOKEN_A1>",
        "medication_name": "Ozempic 2mg/3mL",
        "ndc_code": "00169-4132-12",
        "copay_amount": 25.0,
        "clinical_justification": "Type 2 diabetes with prior metformin therapy."
    }

    result = env["coordinator"].execute_prescription_saga(payload)

    assert result["status"] == "SUCCESS_COMMITTED"

    # Verify PostgreSQL state
    pg_order = env["postgres"].get_order(order_id)
    assert pg_order is not None
    assert pg_order["status"] == "COMMITTED"

    # Verify MongoDB state
    mongo_bundle = env["mongo"].get_bundle(order_id)
    assert mongo_bundle is not None
    assert mongo_bundle["workflow_status"] == "COMMITTED"

    # Verify IBM DB2 Core Claims state
    db2_claim = env["db2"].get_claim(f"CLM-{order_id}")
    assert db2_claim is not None
    assert db2_claim["status"] == "ADJUDICATED_COMMITTED"

def test_saga_compensates_on_db2_timeout(test_environment):
    env = test_environment
    order_id = "ORD-TEST-1002"
    idempotency_key = "IDEMP-KEY-9902"

    payload = {
        "order_id": order_id,
        "idempotency_key": idempotency_key,
        "patient_token": "<PATIENT_TOKEN_B2>",
        "medication_name": "Trulicity 1.5mg",
        "ndc_code": "00002-1433-80",
        "copay_amount": 30.0
    }

    # Inject timeout in DB2 Mainframe
    env["db2"].simulate_timeout = True

    result = env["coordinator"].execute_prescription_saga(payload)

    assert result["status"] == "COMPENSATED_FAILED"

    # Verify PostgreSQL was rolled back cleanly (zero orphan active order)
    pg_order = env["postgres"].get_order(order_id)
    assert pg_order["status"] == "ROLLED_BACK_SAGA_ABORT"

    # Verify MongoDB bundle marked as aborted
    mongo_bundle = env["mongo"].get_bundle(order_id)
    assert mongo_bundle["workflow_status"] == "ABORTED_ORPHAN_PREVENTED"

    # Verify DB2 has zero active claims
    db2_claim = env["db2"].get_claim(f"CLM-{order_id}")
    assert db2_claim is None

def test_idempotency_prevents_duplicate_race_condition(test_environment):
    env = test_environment
    order_id = "ORD-TEST-1003"
    idempotency_key = "SHARED-LOCK-KEY-1"

    # Simulate active lock acquisition
    acquired = env["postgres"].acquire_idempotency_lock(idempotency_key)
    assert acquired is True

    # Immediate second attempt with same key must be rejected
    second_attempt = env["coordinator"].execute_prescription_saga({
        "order_id": order_id,
        "idempotency_key": idempotency_key
    })

    assert second_attempt["status"] == "REJECTED_CONCURRENT_TRANSACTION"
