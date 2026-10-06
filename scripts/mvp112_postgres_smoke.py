from datetime import datetime, timezone
from uuid import uuid4

from src.incident.case_builder import IncidentCase
from src.incident.persistence_adapter import persist_incident_case
from src.dedup.persistence import process_event


unique = uuid4().hex[:12]
now = datetime.now(timezone.utc).isoformat()

incident = IncidentCase(
    schema_version="1.0",
    environment="LAB",
    incident_id=f"INC-LAB-{unique}",
    ioc_type="domain",
    ioc_value=f"malicious-{unique}.test",
    ioc_fingerprint=("a" * 52) + unique,
    source_event_id=f"SOURCE-LAB-{unique}",
    threat_provider="TEST",
    threat_known=True,
    threat_reputation="MALICIOUS",
    threat_score=95,
    risk_score=100,
    risk_level="CRITICAL",
    policy_decision="ESCALATE",
    status="ESCALATED",
    summary="MVP1.12 PostgreSQL LAB persistence test",
    reasons=("synthetic_lab_test",),
    operational_action_allowed=False,
    human_review_required=True,
    human_review_completed=False,
)

collection_id = f"LAB-MVP112-{unique}"

result = persist_incident_case(
    incident=incident,
    occurred_at=now,
    collection_id=collection_id,
    collection_sequence=1,
    process_func=process_event,
)

print("INCIDENT_ID=", incident.incident_id)
print("COLLECTION_ID=", collection_id)
print("STATUS=", result.get("status"))
print("SHOULD_ANALYZE=", result.get("should_analyze"))
print("INVESTIGATION_ID=", result.get("investigation_id"))
print("VERSION=", result.get("investigation_version"))
print("QUEUE_ID=", result.get("queue_id"))
