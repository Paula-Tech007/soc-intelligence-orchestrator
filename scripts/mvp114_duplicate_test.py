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

    risk_score=risk_data["risk_score"],
    risk_level=risk_data["risk_level"],

    policy_decision=policy_data["decision"],
    status=policy_data["status"],

    summary="MVP1.14 exact-repeat validation",
    reasons=("synthetic_duplicate_test",),

    operational_action_allowed=False,
    human_review_required=True,
    human_review_completed=False,
)


collection_id = (
    "LAB-MVP114-"
    + uuid4().hex[:12]
)

result = persist_incident_case(
    incident=incident,

    # Precisa ser exatamente o occurred_at original.
    occurred_at=event["occurred_at"],

    # Nova coleta, portanto collection_id diferente.
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
