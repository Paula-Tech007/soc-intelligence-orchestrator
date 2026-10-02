"""
AI Review Orchestrator - LAB/MOCK.

Gate -> Adapter -> AnalysisCache -> WF-04 result validation.

Nao disponibiliza parametro para injetar modelo real.
Nao executa Ollama, banco, rede ou notificacoes.
"""

import json

from types import SimpleNamespace

from src.ai_engine.cache import AnalysisCache
from src.ai_engine.integrity import validate_result
from src.ai_engine.review_adapter import prepare_mock_review_context


MOCK_MODEL_ID = "SOC-LAB-DETERMINISTIC-MOCK-V1"


class _FixedMockModel:
    """Modelo offline com resposta assistiva deterministica."""

    def __init__(self, evidence_ids):
        self.evidence_ids = list(evidence_ids)
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1

        if len(messages) != 2:
            raise ValueError("Contrato de mensagens inesperado.")

        response = {
            "summary": (
                "Evento sintetico encaminhado para revisao humana."
            ),
            "assessment": (
                "As evidencias disponiveis permitem uma "
                "revisao assistiva, sem conclusao operacional."
            ),
            "evidence_ids": self.evidence_ids,
            "limitations": [
                "Analise inteiramente simulada.",
                "Nenhuma inferencia sobre ambientes reais.",
            ],
            "review_actions": [
                "Revisar as evidencias sinteticas registradas.",
            ],
        }

        return SimpleNamespace(
            content=json.dumps(response, ensure_ascii=False)
        )


def run_mock_review(envelope, *, cache=None):
    """
    Executa somente uma simulacao offline do WF-04.

    Contextos historicos ou bloqueados retornam antes
    da construcao do modelo MOCK.
    """

    prepared = prepare_mock_review_context(envelope)

    base = {
        "schema_version": "1.0",
        "environment": "LAB",
        "processor": "AI_REVIEW_ORCHESTRATOR",
        "queue_id": prepared["queue_id"],
        "gate_decision": prepared["gate_decision"],
        "review_status": prepared["review_status"],
        "wf04_result": None,
        "fixture_type": "MOCK_AI_RESPONSE",
        "real_ollama_call": False,
        "model_invoked_this_call": False,
        "operational_dispatch_allowed": False,
        "ready_for_operational_dispatch": False,
        "notification_sent": False,
        "human_review_required": True,
    }

    if prepared["review_status"] != "MOCK_CONTEXT_PREPARED":
        return base

    if cache is None:
        cache = AnalysisCache()

    if type(cache) is not AnalysisCache:
        raise TypeError("Cache MOCK deve ser AnalysisCache.")

    context = prepared["wf04_context"]

    evidence_ids = [
        item["evidence_id"]
        for item in context["event"]["evidence"]
    ]

    model = _FixedMockModel(evidence_ids)

    result = cache.run_mock(
        context,
        model=model,
        model_id=MOCK_MODEL_ID,
    )

    # Marcadores reproduzem o contrato MOCK utilizado
    # anteriormente no projeto.
    result = {
        **result,
        "fixture_type": "MOCK_AI_RESPONSE",
        "real_ollama_call": False,
        "ready_for_operational_dispatch": False,
    }

    # O resultado precisa atender ao contrato de integridade
    # antes de ser disponibilizado ao proximo componente.
    validate_result(result)

    return {
        **base,
        "review_status": "MOCK_ANALYSIS_COMPLETED",
        "wf04_result": result,
        "model_invoked_this_call": result[
            "model_invoked_this_call"
        ],
    }
