"""
Etapa 10 - Integridade offline da revisao MOCK.

Nao acessa PostgreSQL, Ollama, HTTP ou sistemas corporativos.
Nao persiste resultados e nao realiza notificacoes.
"""

import copy

from src.ai_engine.review_orchestrator import run_mock_review

from src.ai_engine.integrity import (
    build_integrity_record,
    verify_integrity_record,
)


def run_verified_mock_review(envelope, *, cache=None):
    """
    Executa o pipeline LAB/MOCK e verifica sua integridade.

    Apenas MOCK_ANALYSIS_COMPLETED produz registro de integridade.

    Se a verificacao falhar, a funcao interrompe o processamento
    sem disponibilizar um contrato marcado como verificado.
    """

    review = run_mock_review(envelope, cache=cache)

    base = {
        **review,
        "integrity_status": "NOT_APPLICABLE",
        "integrity_record": None,
        "verified_against_database": False,
        "operational_dispatch_allowed": False,
        "ready_for_operational_dispatch": False,
        "notification_sent": False,
        "human_review_required": True,
        "real_ollama_call": False,
    }

    if review["review_status"] != "MOCK_ANALYSIS_COMPLETED":
        return base

    result = review.get("wf04_result")

    if not isinstance(result, dict):
        raise ValueError("Resultado WF-04 ausente.")

    if (
        result.get("real_ollama_call") is not False
        or result.get("ready_for_operational_dispatch") is not False
        or result.get("notification_sent") is not False
    ):
        raise ValueError("Resultado fora do escopo LAB/MOCK.")

    # Reutilizar o validador e os hashes oficiais.
    record = build_integrity_record(result)

    if verify_integrity_record(record) is not True:
        raise ValueError("Verificacao de integridade nao confirmada.")

    return {
        **base,
        "integrity_status": "VERIFIED_IN_MEMORY",
        "integrity_record": copy.deepcopy(record),
    }
