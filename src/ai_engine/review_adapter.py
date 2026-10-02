"""
Adaptador entre o Context Decision Gate e o WF-04.

Apenas prepara e valida o contrato para uma futura revisao MOCK.

Nao chama analyze(), ChatOllama, HTTP ou PostgreSQL.
"""

import copy

from src.context.decision_gate import (
    BLOCKED,
    HISTORICAL,
    READY,
    evaluate_context,
)

from src.ai_engine.engine import validate_context


def _blocked_decision(decision, reason):
    """Converte uma falha de validacao em bloqueio seguro."""

    return {
        **decision,
        "decision": BLOCKED,
        "reason_code": reason,
        "eligible_for_ai_review": False,
        "ai_execution_allowed": False,
        "operational_dispatch_allowed": False,
        "human_review_required": True,
        "notification_sent": False,
    }


def prepare_mock_review_context(envelope):
    """
    Recebe o envelope HTTP LAB e prepara o contrato WF-04.

    Apenas READY_FOR_AI_REVIEW pode produzir wf04_context.

    O resultado ainda nao representa uma analise executada.
    """

    gate = evaluate_context(envelope)

    base = {
        "schema_version": "1.0",
        "environment": "LAB",
        "processor": "AI_REVIEW_ADAPTER",
        "queue_id": gate["queue_id"],
        "gate_decision": gate,
        "wf04_context": None,
        "ai_executed": False,
        "real_ollama_call": False,
        "operational_dispatch_allowed": False,
        "notification_sent": False,
        "human_review_required": True,
    }

    if gate["decision"] == HISTORICAL:
        return {
            **base,
            "review_status": "HISTORICAL_SKIPPED",
        }

    if gate["decision"] != READY:
        return {
            **base,
            "review_status": "BLOCKED",
        }

    # O Gate e recalculado neste proprio adaptador.
    # Nunca confiar em uma decisao externa fornecida pelo chamador.
    context = copy.deepcopy(envelope["context"])

    context["validation_status"] = "VALID"
    context["real_execution_started"] = False
    context["ai_executed"] = False
    context["notification_sent"] = False

    context["decision"] = {
        "eligible_for_ai": True,
        "target_workflow": "WF-04",
    }

    # Segunda validacao: requisitos reais do motor WF-04.
    # Exemplo: identidade do evento, evidencias e proveniencia.
    try:
        validation = validate_context(context)
    except (ValueError, TypeError, KeyError):
        return {
            **base,
            "gate_decision": _blocked_decision(
                gate,
                "WF04_CONTEXT_VALIDATION_FAILED",
            ),
            "review_status": "BLOCKED",
        }

    if validation["eligible"] is not True:
        return {
            **base,
            "gate_decision": _blocked_decision(
                gate,
                "WF04_NOT_ELIGIBLE",
            ),
            "review_status": "BLOCKED",
        }

    return {
        **base,
        "review_status": "MOCK_CONTEXT_PREPARED",
        "wf04_context": context,
    }
