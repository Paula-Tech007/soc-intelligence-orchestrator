"""
Etapa 15 - Adaptador integrado LAB/MOCK para WF-05.

Consolida a versao historica e a analise atual ja verificadas.

Nao consulta banco, nao chama Ollama, nao executa HTTP,
nao persiste arquivos e nao envia notificacoes.

O envelope historico deve ser fornecido pelo cliente
de contexto validado ou por uma fixture SOC-LAB homologada.
"""

import copy

from src.ai_engine.integrity import (
    build_integrity_record,
    verify_integrity_record,
)

from src.context.decision_gate import evaluate_context

from src.reports.report_builder import (
    build_report,
    validate_contract,
)


def _observed_result(observed, queue_id, gate, review, integrity):
    """Confere a consistencia entre resultado e telemetria."""

    if not isinstance(observed, dict):
        raise ValueError("Resultado observado invalido.")

    result = observed.get("result")
    telemetry = observed.get("telemetry")

    if not isinstance(result, dict) or not isinstance(telemetry, dict):
        raise ValueError("Envelope de observabilidade invalido.")

    if (
        result.get("queue_id") != queue_id
        or result.get("gate_decision", {}).get("decision") != gate
        or result.get("review_status") != review
        or result.get("integrity_status") != integrity
    ):
        raise ValueError("Resultado integrado inconsistente.")

    if (
        telemetry.get("gate_decision") != gate
        or telemetry.get("review_status") != review
        or telemetry.get("integrity_status") != integrity
        or telemetry.get("pipeline_status") != "COMPLETED"
        or telemetry.get("environment") != "LAB"
        or telemetry.get("error_category") is not None
    ):
        raise ValueError("Telemetria divergente do resultado.")

    if (
        result.get("real_ollama_call") is not False
        or result.get("operational_dispatch_allowed") is not False
        or result.get("ready_for_operational_dispatch") is not False
        or result.get("notification_sent") is not False
        or result.get("human_review_required") is not True
        or result.get("verified_against_database") is not False
    ):
        raise ValueError("Resultado fora das restricoes LAB.")

    return result


def assemble_integrated_mock_contract(
    historical_observed,
    current_observed,
    *,
    historical_envelope,
):
    """
    Prepara o contrato oficial WF-05 a partir de duas
    execucoes observadas do pipeline LAB/MOCK.

    Nao transforma a versao historica em analise executada.
    """

    historical = _observed_result(
        historical_observed,
        12,
        "HISTORICAL_CONTEXT",
        "HISTORICAL_SKIPPED",
        "NOT_APPLICABLE",
    )

    current = _observed_result(
        current_observed,
        13,
        "READY_FOR_AI_REVIEW",
        "MOCK_ANALYSIS_COMPLETED",
        "VERIFIED_IN_MEMORY",
    )

    if (
        historical.get("wf04_result") is not None
        or historical.get("integrity_record") is not None
        or historical.get("model_invoked_this_call") is not False
        or historical_observed["telemetry"].get("cache_hit") is not None
    ):
        raise ValueError("Historico indevidamente promovido.")

    if not isinstance(historical_envelope, dict):
        raise ValueError("Envelope historico invalido.")

    gate = evaluate_context(historical_envelope)

    if (
        gate.get("decision") != "HISTORICAL_CONTEXT"
        or gate.get("queue_id") != 12
    ):
        raise ValueError("Contexto historico nao confirmado.")

    context = historical_envelope.get("context")

    if not isinstance(context, dict):
        raise ValueError("Contexto historico ausente.")

    if (
        context.get("requested_version") != 1
        or context.get("current_version") != 2
        or context.get("is_historical_version") is not True
        or context.get("ai_executed") is not False
        or context.get("notification_sent") is not False
        or context.get("dispatch_status") != "MOCK_ONLY"
    ):
        raise ValueError("Estado historico inconsistente.")

    wf04 = current.get("wf04_result")
    record = current.get("integrity_record")

    if not isinstance(wf04, dict) or not isinstance(record, dict):
        raise ValueError("Analise ou integridade ausente.")

    if (
        wf04.get("queue_id") != 13
        or wf04.get("investigation_version") != 2
        or wf04.get("status") != "ANALYSIS_COMPLETED"
        or wf04.get("real_ollama_call") is not False
        or wf04.get("ready_for_operational_dispatch") is not False
        or wf04.get("notification_sent") is not False
        or wf04.get("requires_human_review") is not True
    ):
        raise ValueError("Resultado WF-04 atual invalido.")

    if (
        current_observed["telemetry"].get("cache_hit")
        is not wf04.get("cache_hit")
    ):
        raise ValueError("Metrica de cache divergente.")

    if verify_integrity_record(record) is not True:
        raise ValueError("Integridade da analise nao confirmada.")

    expected_record = build_integrity_record(wf04)

    if expected_record != record:
        raise ValueError("Integridade nao corresponde ao WF-04.")

    for field in ("investigation_id", "source_event_id"):
        if context.get(field) != wf04.get(field):
            raise ValueError("Identidade historica divergente.")

    historical_item = {
        "schema_version": "1.0",
        "environment": "LAB",
        "processor": "WF-04",
        "investigation_id": context["investigation_id"],
        "source_event_id": context["source_event_id"],
        "investigation_version": 1,
        "queue_id": 12,
        "status": "SKIPPED",
        "reason": "Contexto nao elegivel para IA.",
        "analysis": None,
        "provenance": copy.deepcopy(context["provenance"]),
        "dispatch_status": "MOCK_ONLY",
        "real_execution_started": False,
        "ai_executed": False,
        "notification_sent": False,
        "requires_human_review": False,
    }

    current_item = copy.deepcopy(wf04)

    contract = {
        "schema_version": "1.0",
        "environment": "LAB",
        "origin": "WF-04",
        "fixture_type": "MOCK_AI_RESPONSE",
        "real_ollama_call": False,
        "ready_for_operational_dispatch": False,
        "results": [
            historical_item,
            current_item,
        ],
    }

    # O validador oficial permanece sendo a autoridade
    # para a estrutura exigida pelo gerador WF-05.
    validate_contract(contract)

    return contract


def build_integrated_mock_report(
    historical_observed,
    current_observed,
    *,
    historical_envelope,
):
    """Gera HTML em memoria somente apos a validacao oficial."""

    contract = assemble_integrated_mock_contract(
        historical_observed,
        current_observed,
        historical_envelope=historical_envelope,
    )

    html = build_report(contract)

    return {
        "schema_version": "1.0",
        "environment": "LAB",
        "report_type": "WF05_INTEGRATED_MOCK",
        "integrity_status": "VERIFIED_IN_MEMORY",
        "verified_against_database": False,
        "human_review_required": True,
        "operational_dispatch_allowed": False,
        "notification_sent": False,
        "html": html,
    }
