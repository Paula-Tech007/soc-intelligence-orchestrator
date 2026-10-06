from uuid import uuid4

from src.dedup.persistence import connect_db, process_event
from src.incident.case_builder import IncidentCase
from src.incident.persistence_adapter import persist_incident_case


INVESTIGATION_ID = "d8f55806-128b-434e-88f7-1d956a63242e"

with connect_db() as connection:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT latest_event
            FROM investigations
            WHERE id = %s
            """,
            (INVESTIGATION_ID,),
        )

        row = cursor.fetchone()

        if not row:
            raise RuntimeError(
                "Investigacao MVP1.13 nao encontrada."
            )

        event = row["latest_event"]


entity = event["entity"]
evidence = event["evidence"]

threat = next(
    item for item in evidence
    if item["type"] == "threat_intelligence"
)

risk_data = next(
    item for item in evidence
    if item["type"] == "risk_assessment"
)

policy_data = next(
    item for item in evidence
    if item["type"] == "policy_decision"
)


incident = IncidentCase(
    schema_version="1.0",
    environment="LAB",

    # Mesma identidade do incidente
    incident_id=event["source_event_id"],

    ioc_type=entity["ioc_type"],
    ioc_value=entity["ioc_value"],
    ioc_fingerprint=entity["ioc_fingerprint"],

    source_event_id=
        entity["original_source_event_id"],

    threat_provider=threat["provider"],
    threat_known=threat["known"],
    threat_reputation=threat["reputation"],
    threat_score=threat["threat_score"],

    # Alteracao material controlada
    risk_score=75,
    risk_level="HIGH",

    policy_decision="ESCALATE",
    status="ESCALATED",

    summary="MVP1.15 material update validation",
    reasons=("synthetic_material_update",),

    operational_action_allowed=False,
    human_review_required=True,
    human_review_completed=False,
)


collection_id = (
    "LAB-MVP115-"
    + uuid4().hex[:12]
)

result = persist_incident_case(
    incident=incident,

    # Mantemos o occurred_at original.
    occurred_at=event["occurred_at"],

    collection_id=collection_id,
    collection_sequence=1,

    process_func=process_event,
)


print("COLLECTION_ID=", collection_id)
print("STATUS=", result.get("status"))
print(
    "SHOULD_ANALYZE=",
    result.get("should_analyze"),
)
print(
    "INVESTIGATION_ID=",
    result.get("investigation_id"),
)
print(
    "VERSION=",
    result.get("investigation_version"),
)
print(
    "OCCURRENCE_COUNT=",
    result.get("occurrence_count"),
)
print(
    "CHANGED_FIELDS=",
    result.get("changed_fields"),
)
print(
    "NEW_EVIDENCE_IDS=",
    result.get("new_evidence_ids"),
)
