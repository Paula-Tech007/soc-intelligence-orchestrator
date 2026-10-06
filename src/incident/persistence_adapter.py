"""IncidentCase -> existing SOC persistence contract.

MVP1.11

This module does not implement a second persistence system.
It adapts IncidentCase into the existing src.dedup.persistence
process_event contract.

No network.
No direct SQL.
No operational action.
"""

from __future__ import annotations

from typing import Any, Callable

from src.incident.case_builder import IncidentCase


class IncidentPersistenceAdapterError(ValueError):
    """Raised when IncidentCase cannot be safely adapted."""


RISK_TO_SEVERITY = {
    "LOW": "low",
    "MEDIUM": "medium",
    "HIGH": "high",
    "CRITICAL": "critical",
}


def incident_case_to_persistence_payload(
    *,
    incident: IncidentCase,
    occurred_at: str,
    collection_id: str,
    collection_sequence: int,
) -> dict[str, Any]:

    if not isinstance(incident, IncidentCase):
        raise IncidentPersistenceAdapterError(
            "incident deve ser IncidentCase."
        )

    if incident.environment != "LAB":
        raise IncidentPersistenceAdapterError(
            "somente IncidentCase LAB permitido."
        )

    if incident.operational_action_allowed:
        raise IncidentPersistenceAdapterError(
            "acao operacional deve permanecer bloqueada."
        )

    if not incident.human_review_required:
        raise IncidentPersistenceAdapterError(
            "revisao humana deve permanecer obrigatoria."
        )

    if incident.human_review_completed:
        raise IncidentPersistenceAdapterError(
            "revisao humana nao pode estar concluida nesta etapa."
        )

    if (
        not isinstance(occurred_at, str)
        or not occurred_at.strip()
    ):
        raise IncidentPersistenceAdapterError(
            "occurred_at obrigatorio."
        )

    if (
        not isinstance(collection_id, str)
        or not collection_id.strip()
    ):
        raise IncidentPersistenceAdapterError(
            "collection_id obrigatorio."
        )

    if (
        type(collection_sequence) is not int
        or collection_sequence <= 0
    ):
        raise IncidentPersistenceAdapterError(
            "collection_sequence invalido."
        )

    try:
        severity = RISK_TO_SEVERITY[
            incident.risk_level
        ]
    except KeyError as exc:
        raise IncidentPersistenceAdapterError(
            f"risk_level invalido: {incident.risk_level}"
        ) from exc

    raw_event = {
        "source_event_id": incident.incident_id,
        "occurred_at": occurred_at,
        "event_type": "ioc_incident",
        "severity": severity,
        "entity": {
            "ioc_type": incident.ioc_type,
            "ioc_value": incident.ioc_value,
            "ioc_fingerprint": incident.ioc_fingerprint,
            "original_source_event_id":
                incident.source_event_id,
        },
        "evidence": [
            {
                "evidence_id":
                    f"{incident.incident_id}-THREAT",
                "type": "threat_intelligence",
                "provider": incident.threat_provider,
                "known": incident.threat_known,
                "reputation":
                    incident.threat_reputation,
                "threat_score":
                    incident.threat_score,
            },
            {
                "evidence_id":
                    f"{incident.incident_id}-RISK",
                "type": "risk_assessment",
                "risk_score": incident.risk_score,
                "risk_level": incident.risk_level,
            },
            {
                "evidence_id":
                    f"{incident.incident_id}-POLICY",
                "type": "policy_decision",
                "decision":
                    incident.policy_decision,
                "status": incident.status,
            },
        ],
    }

    return {
        "schema_version": "1.0",
        "environment": "LAB",
        "source": "SOC-LAB",
        "collection_id": collection_id,
        "collection_sequence":
            collection_sequence,
        "raw_event": raw_event,
    }


def persist_incident_case(
    *,
    incident: IncidentCase,
    occurred_at: str,
    collection_id: str,
    collection_sequence: int,
    process_func: Callable[
        [dict[str, Any]],
        dict[str, Any],
    ],
) -> dict[str, Any]:

    if not callable(process_func):
        raise IncidentPersistenceAdapterError(
            "process_func deve ser callable."
        )

    payload = incident_case_to_persistence_payload(
        incident=incident,
        occurred_at=occurred_at,
        collection_id=collection_id,
        collection_sequence=collection_sequence,
    )

    result = process_func(payload)

    if not isinstance(result, dict):
        raise IncidentPersistenceAdapterError(
            "resultado da persistencia invalido."
        )

    return result
