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
    current_envelope=None,
):
    """
    Prepara o contrato oficial WF-05 a partir de duas
    execucoes observadas do pipeline LAB/MOCK.

    Nao transforma a versao historica em analise executada.
    """

    generic = current_envelope is not None

    expected_historical_queue = 12
    expected_current_queue = 13
    expected_historical_version = 1
    expected_current_version = 2
    trusted_evidence = None
    current_context = None

    if generic:
        if (
            not isinstance(historical_envelope, dict)
            or not isinstance(current_envelope, dict)
        ):
            raise ValueError("Context envelopes required.")

        historical_context = historical_envelope.get("context")
        current_context = current_envelope.get("context")

        if (
            not isinstance(historical_context, dict)
            or not isinstance(current_context, dict)
        ):
            raise ValueError("Investigation contexts missing.")

        historical_gate = evaluate_context(historical_envelope)
        current_gate = evaluate_context(current_envelope)

        if (
            historical_gate.get("decision") != "HISTORICAL_CONTEXT"
            or current_gate.get("decision") != "READY_FOR_AI_REVIEW"
        ):
            raise ValueError("Invalid historical/current gate pairing.")

        expected_historical_queue = historical_context.get("queue_id")
        expected_current_queue = current_context.get("queue_id")

        expected_historical_version = historical_context.get(
            "requested_version"
        )
        expected_current_version = current_context.get(
            "requested_version"
        )

        if (
            type(expected_historical_queue) is not int
            or type(expected_current_queue) is not int
            or expected_historical_queue < 1
            or expected_current_queue < 1
            or expected_historical_queue == expected_current_queue
            or historical_gate.get("queue_id")
            != expected_historical_queue
            or current_gate.get("queue_id")
            != expected_current_queue
            or type(expected_historical_version) is not int
            or type(expected_current_version) is not int
            or expected_current_version
            != expected_historical_version + 1
            or historical_context.get("current_version")
            != expected_current_version
            or current_context.get("current_version")
            != expected_current_version
        ):
            raise ValueError("Investigation version or queue mismatch.")

        for field in ("investigation_id", "source_event_id"):
            value = historical_context.get(field)

            if (
                not isinstance(value, str)
                or not value.strip()
                or value != current_context.get(field)
            ):
                raise ValueError("Investigation identity mismatch.")

        event = current_context.get("event")

        if (
            not isinstance(event, dict)
            or event.get("source_event_id")
            != current_context["source_event_id"]
        ):
            raise ValueError("Current event identity mismatch.")

        evidence = event.get("evidence")

        if not isinstance(evidence, list) or not evidence:
            raise ValueError("Trusted evidence missing.")

        trusted_evidence = []

        for item in evidence:
            if not isinstance(item, dict):
                raise ValueError("Invalid trusted evidence.")

            evidence_id = item.get("evidence_id")

            if (
                not isinstance(evidence_id, str)
                or not evidence_id.strip()
            ):
                raise ValueError("Invalid trusted evidence ID.")

            trusted_evidence.append(evidence_id)

        if (
            len(set(trusted_evidence)) != len(trusted_evidence)
            or current_context.get("evidence_count")
            != len(trusted_evidence)
        ):
            raise ValueError("Trusted evidence count mismatch.")

    historical = _observed_result(
        historical_observed,
        expected_historical_queue,
        "HISTORICAL_CONTEXT",
        "HISTORICAL_SKIPPED",
        "NOT_APPLICABLE",
    )

    current = _observed_result(
        current_observed,
        expected_current_queue,
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
        or gate.get("queue_id") != expected_historical_queue
    ):
        raise ValueError("Contexto historico nao confirmado.")

    context = historical_envelope.get("context")

    if not isinstance(context, dict):
        raise ValueError("Contexto historico ausente.")

    if (
        context.get("requested_version")
        != expected_historical_version
        or context.get("current_version")
        != expected_current_version
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
        wf04.get("queue_id") != expected_current_queue
        or wf04.get("investigation_version")
        != expected_current_version
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

    if generic:
        if (
            current_context["investigation_id"]
            != wf04.get("investigation_id")
            or current_context["source_event_id"]
            != wf04.get("source_event_id")
            or current_context.get("provenance")
            != wf04.get("provenance")
        ):
            raise ValueError(
                "Current context and signed WF-04 result diverge."
            )

    historical_item = {
        "schema_version": "1.0",
        "environment": "LAB",
        "processor": "WF-04",
        "investigation_id": context["investigation_id"],
        "source_event_id": context["source_event_id"],
        "investigation_version": expected_historical_version,
        "queue_id": expected_historical_queue,
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
    validate_contract(
        contract,
        expected_evidence_ids=trusted_evidence,
    )

    return contract


def build_integrated_mock_report(
    historical_observed,
    current_observed,
    *,
    historical_envelope,
    current_envelope=None,
):
    """Gera HTML em memoria somente apos a validacao oficial."""

    contract = assemble_integrated_mock_contract(
        historical_observed,
        current_observed,
        historical_envelope=historical_envelope,
        current_envelope=current_envelope,
    )

    trusted_evidence = None

    if current_envelope is not None:
        trusted_evidence = [
            item["evidence_id"]
            for item in current_envelope["context"]["event"]["evidence"]
        ]

    html = build_report(
        contract,
        expected_evidence_ids=trusted_evidence,
    )

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
