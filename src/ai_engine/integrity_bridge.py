"""
FASE 13.5.3 - Adaptador WF-04 -> WF-05.

Escopo: LAB/MOCK.
Sem banco, Ollama ou operacoes externas.

Preserva a proveniencia original e adiciona um registro
independente para verificar a integridade da analise.
"""

import copy

from src.ai_engine.integrity import (
    IntegrityRegistry,
    build_integrity_record,
    verify_integrity_record,
)

from src.reports.report_builder import validate_contract


def prepare_integrity_contract(envelope, registry=None):

    # Validar primeiro o contrato completo recebido.
    historical, current = validate_contract(envelope)

    if registry is None:
        registry = IntegrityRegistry()

    # O fixture original nao inclui todos os campos de
    # transporte adicionados posteriormente pelo n8n.
    # Enriquecemos apenas uma copia, preservando a fonte.
    current_result = copy.deepcopy(current)

    current_result.update({
        "fixture_type": "MOCK_AI_RESPONSE",
        "real_ollama_call": False,
        "ready_for_operational_dispatch": False,
    })

    record = build_integrity_record(current_result)

    verify_integrity_record(record)

    registry_status = registry.register(record)

    result = copy.deepcopy(envelope)

    result["integrity"] = {
        "schema_version": "1.0",
        "mode": "LAB_MOCK",
        "status": "VALID",
        "registry_status": registry_status,
        "investigation_version": current["investigation_version"],
        "content_signature": record["content_signature"],
        "analysis_signature": record["analysis_signature"],
        "result_key": record["result_key"],
        "verified_against_database": False,
        "operational_dispatch_allowed": False,
    }

    result["handoff"] = {
        "source": "WF-04",
        "target": "WF-05",
        "historical_queue_id": historical["queue_id"],
        "selected_queue_id": current["queue_id"],
        "selected_version": current["investigation_version"],
        "status": "READY_FOR_MOCK_REPORT",
        "human_review_required": True,
        "operational_dispatch_allowed": False,
    }

    return result
