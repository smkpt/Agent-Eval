"""Unit tests verifying component health probes and status degradation."""
from src.telemetry.health import ComponentHealthCheck
from src.storage.mongo_client import MongoClient
from src.storage.postgres_client import PostgresClient
from src.storage.db2_client import DB2Client

def test_component_health_all_healthy():
    mongo = MongoClient()
    postgres = PostgresClient()
    db2 = DB2Client()
    checker = ComponentHealthCheck(mongo=mongo, postgres=postgres, db2=db2)

    report = checker.check_all()
    assert report["system_status"] == "HEALTHY"
    assert report["healthy_count"] == report["total_components"]
    assert report["components"]["mongodb"]["status"] == "HEALTHY"
    assert report["components"]["postgresql"]["status"] == "HEALTHY"
    assert report["components"]["ibm_db2"]["status"] == "HEALTHY"

def test_component_health_degrades_on_db2_timeout():
    mongo = MongoClient()
    postgres = PostgresClient()
    db2 = DB2Client()
    # Inject DB2 timeout
    db2.simulate_timeout = True

    checker = ComponentHealthCheck(mongo=mongo, postgres=postgres, db2=db2)
    report = checker.check_all()

    assert report["system_status"] == "DEGRADED"
    assert report["components"]["ibm_db2"]["status"] == "DEGRADED"
    assert "Simulated DRDA" in report["components"]["ibm_db2"]["error"]
