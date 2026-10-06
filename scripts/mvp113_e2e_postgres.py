from datetime import datetime, timezone
from uuid import uuid4

from src.ioc.contract import build_canonical_ioc
from src.threat_intel.contract import build_threat_intel_result
from src.risk.ioc_risk import assess_ioc_risk
from src.policy.risk_policy import evaluate_risk_policy
from src.incident.case_builder import build_incident_case
from src.incident.persistence_adapter import persist_incident_case
from src.dedup.persistence import process_event


unique = uuid4().hex[:12]
now = datetime.now(timezone.utc).isoformat()

ioc = build_canonical_ioc({
    "schema_version": "1.0",
    "environment": "LAB",
    "ioc_type": "domain",
    "value": f"malicious-{unique}.test",
    "source": "MVP1.13-E2E",
    "source_event_id": f"E2E-{unique}",
    "observed_at": now,
    "severity": "HIGH",
    "confidence": 95,
})

intel = build_threat_intel_result(
    provider="E2E-MOCK",
    ioc_type=ioc.ioc_type,
    ioc_value=ioc.normalized_value,
    ioc_fingerprint=ioc.fingerprint,
    known=True,
    reputation="MALICIOUS",
    confidence=95,
    threat_score=95,
    sources=["E2E-MOCK"],
    tags=["synthetic", "mvp1.13"],
)

risk = assess_ioc_risk(
    ioc=ioc,
    threat_intel=intel,
)

policy = evaluate_risk_policy(
    risk=risk,
)

incident = build_incident_case(
    ioc=ioc,
    threat_intel=intel,
    risk=risk,
    policy=policy,
)

collection_id = f"LAB-MVP113-{unique}"

result = persist_incident_case(
    incident=incident,
    occurred_at=now,
    collection_id=collection_id,
    collection_sequence=1,
    process_func=process_event,
)

print("IOC=", ioc.normalized_value)
print("REPUTATION=", intel.reputation)
print("RISK_SCORE=", risk.risk_score)
print("RISK_LEVEL=", risk.risk_level)
print("POLICY=", policy.decision)
print("INCIDENT_ID=", incident.incident_id)
print("INCIDENT_STATUS=", incident.status)
print("COLLECTION_ID=", collection_id)
print("PERSISTENCE_STATUS=", result.get("status"))
print("SHOULD_ANALYZE=", result.get("should_analyze"))
print("INVESTIGATION_ID=", result.get("investigation_id"))
print("VERSION=", result.get("investigation_version"))
