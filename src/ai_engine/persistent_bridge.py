"""
SOC Intelligence Orchestrator
FASE 13.8.3 - Persistent Integrity Bridge

Integra o contrato MOCK do WF-04 com a persistencia
transacional do PostgreSQL.

Nenhum despacho operacional e permitido.
"""

import copy

from src.ai_engine.integrity import (
    build_integrity_record,
    verify_integrity_record,
)

from src.ai_engine.integrity_bridge import (
    prepare_integrity_contract,
)

from src.ai_engine.integrity_persistence import (
    persist_integrity_record,
)

from src.reports.report_builder import (
    validate_contract,
)


class PersistenceContractError(ValueError):
    """Comprovante de persistencia ausente ou inconsistente."""


def prepare_persisted_integrity_contract(envelope):
    """
    Recebe um contrato WF-04 LAB/MOCK e devolve o
    contrato para WF-05 somente apos a confirmacao
    da persistencia no PostgreSQL.

    Resultados esperados da persistencia:
      NEW_RESULT
      ALREADY_REGISTERED

    Em caso de falha, propaga a excecao sem
    devolver contrato autorizado.
    """

    # ------------------------------------------------------
    # 1. VALIDACAO E INTEGRIDADE EM MEMORIA
    # ------------------------------------------------------

    prepared = prepare_integrity_contract(envelope)

    _, current = validate_contract(prepared)

    current_result = copy.deepcopy(current)

    current_result.update({
        "fixture_type": "MOCK_AI_RESPONSE",
        "real_ollama_call": False,
        "ready_for_operational_dispatch": False,
    })

    record = build_integrity_record(current_result)

    verify_integrity_record(record)

    integrity = prepared["integrity"]

    for field in (
        "content_signature",
        "analysis_signature",
        "result_key",
    ):
        if integrity.get(field) != record[field]:
            raise PersistenceContractError(
                "INTEGRITY_CONFLICT: assinatura divergente: "
                + field
            )

    if (
        integrity.get("verified_against_database") is not False
        or integrity.get("operational_dispatch_allowed") is not False
    ):
        raise PersistenceContractError(
            "Estado inicial do contrato invalido."
        )

    # ------------------------------------------------------
    # 2. PERSISTENCIA TRANSACIONAL
    # ------------------------------------------------------

    persistence_result = persist_integrity_record(record)

    if not isinstance(persistence_result, dict):
        raise PersistenceContractError(
            "Comprovante PostgreSQL invalido."
        )

    status = persistence_result.get("status")

    if status not in (
        "NEW_RESULT",
        "ALREADY_REGISTERED",
    ):
        raise PersistenceContractError(
            "Persistencia nao confirmada."
        )

    record_id = persistence_result.get("record_id")

    if type(record_id) is not int or record_id < 1:
        raise PersistenceContractError(
            "Identificador persistido invalido."
        )

    for field in (
        "result_key",
        "analysis_signature",
    ):
        if persistence_result.get(field) != record[field]:
            raise PersistenceContractError(
                "Comprovante PostgreSQL divergente: "
                + field
            )

    if (
        persistence_result.get("verified_against_database")
        is not True
        or persistence_result.get(
            "operational_dispatch_allowed"
        ) is not False
    ):
        raise PersistenceContractError(
            "Comprovante de persistencia nao autorizado."
        )

    # ------------------------------------------------------
    # 3. CONSTRUIR SAIDA SOMENTE APOS CONFIRMACAO
    # ------------------------------------------------------

    output = copy.deepcopy(prepared)

    output["integrity"].update({
        "status": "PERSISTED_VALID",
        "persistence_status": status,
        "database_record_id": record_id,
        "verification_method": "POSTGRESQL_TRANSACTION",
        "verified_against_database": True,
        "operational_dispatch_allowed": False,
    })

    output["handoff"].update({
        "status": "READY_FOR_PERSISTED_MOCK_REPORT",
        "human_review_required": True,
        "operational_dispatch_allowed": False,
    })

    output["ready_for_operational_dispatch"] = False

    return output
