from src.context.context_builder import build_context
from src.risk.ioc_risk import RiskAssessment
from src.risk.correlation_risk import assess_correlation_risk


QUEUE_ID = 17

context = build_context(QUEUE_ID)

event = context["event"]
entity = event["entity"]
evidence = event["evidence"]

risk_data = next(
    item
    for item in evidence
    if item["type"] == "risk_assessment"
)

risk = RiskAssessment(
    schema_version="1.0",
    environment="LAB",

    ioc_fingerprint=
        entity["ioc_fingerprint"],

    risk_score=
        risk_data["risk_score"],

    risk_level=
        risk_data["risk_level"],

    reasons=(
        "loaded_from_persisted_incident",
    ),

    operational_action_allowed=False,
    human_review_required=True,
)

matches = context[
    "correlations"
]["matches"]

aggregated = assess_correlation_risk(
    risk=risk,
    correlation_matches=matches,
)


print("QUEUE_ID=", QUEUE_ID)

print(
    "IOC_VALUE=",
    entity["ioc_value"],
)

print(
    "BASE_RISK_SCORE=",
    aggregated.base_risk_score,
)

print(
    "BASE_RISK_LEVEL=",
    aggregated.base_risk_level,
)

print(
    "CORRELATED_INVESTIGATIONS=",
    aggregated.correlated_investigations,
)

print(
    "CORRELATION_BONUS=",
    aggregated.correlation_bonus,
)

print(
    "AGGREGATED_RISK_SCORE=",
    aggregated.aggregated_risk_score,
)

print(
    "AGGREGATED_RISK_LEVEL=",
    aggregated.aggregated_risk_level,
)

print(
    "OPERATIONAL_ACTION_ALLOWED=",
    aggregated.operational_action_allowed,
)

print(
    "HUMAN_REVIEW_REQUIRED=",
    aggregated.human_review_required,
)

print(
    "REASONS=",
    aggregated.reasons,
)
