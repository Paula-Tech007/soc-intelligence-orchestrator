from uuid import uuid4

from src.dedup.persistence import connect_db, process_event
from src.incident.case_builder import IncidentCase
from src.incident.persistence_adapter import persist_incident_case
from src.context.context_builder import build_context


ORIGINAL_INVESTIGATION_ID = (
    "d8f55806-128b-434e-88f7-1d956a63242e"
)

with connect_db() as connection:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT latest_event
            FROM investigations
            WHERE id = %s
            """,
            (ORIGINAL_INVESTIGATION_ID,),
        )

        row = cursor.fetchone()

        if not row:
            raise RuntimeError(
                "Investigacao original nao encontrada."
            )

        original_event = row["latest_event"]


entity = original_event["entity"]
evidence = original_event["evidence"]

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


unique = uuid4().hex[:12]

incident = IncidentCase(
    schema_version="1.0",
    environment="LAB",

    # Identidade NOVA da investigacao.
    incident_id=f"INC-CORR-{unique}",

    # IOC exatamente igual ao original.
    ioc_type=entity["ioc_type"],
    ioc_value=entity["ioc_value"],
    ioc_fingerprint=entity["ioc_fingerprint"],

    source_event_id=f"CORR-SOURCE-{unique}",

    threat_provider=threat["provider"],
    threat_known=threat["known"],
    threat_reputation=threat["reputation"],
    threat_score=threat["threat_score"],

    risk_score=risk_data["risk_score"],
    risk_level=risk_data["risk_level"],

    policy_decision=policy_data["decision"],
    status=policy_data["status"],

    summary="MVP1.17 IOC correlation E2E",
    reasons=("synthetic_ioc_correlation",),

    operational_action_allowed=False,
    human_review_required=True,
    human_review_completed=False,
)


collection_id = f"LAB-MVP117-{unique}"

result = persist_incident_case(
    incident=incident,
    occurred_at=original_event["occurred_at"],
    collection_id=collection_id,
    collection_sequence=1,
    process_func=process_event,
)

new_investigation_id = result["investigation_id"]


with connect_db() as connection:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM analysis_queue
            WHERE investigation_id = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (new_investigation_id,),
        )

        queue_row = cursor.fetchone()

        if not queue_row:
            raise RuntimeError(
                "Fila da nova investigacao nao encontrada."
            )

        queue_id = queue_row["id"]


context = build_context(queue_id)


print(
    "NEW_INVESTIGATION_ID=",
    new_investigation_id,
)

print(
    "QUEUE_ID=",
    queue_id,
)

print(
    "PERSISTENCE_STATUS=",
    result.get("status"),
)

print(
    "IOC_VALUE=",
    entity["ioc_value"],
)

print(
    "IOC_FINGERPRINT=",
    entity["ioc_fingerprint"],
)

print(
    "CORRELATION_MATCHES=",
    context["correlations"]["matches"],
)
