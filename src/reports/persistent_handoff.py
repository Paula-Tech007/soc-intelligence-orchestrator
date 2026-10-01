"""
SOC Intelligence Orchestrator
FASE 13.9.2 - WF-05 Persistent Handoff Gate

Valida novamente o resultado LAB/MOCK no PostgreSQL
antes de disponibilizar o contrato ao gerador de relatorios.

Somente leitura. Nenhuma acao operacional.
"""

import copy

from psycopg.rows import tuple_row

from src.ai_engine.integrity import (
    build_integrity_record,
    verify_integrity_record,
)

from src.dedup.persistence import connect_db

from src.reports.report_builder import validate_contract


class PersistentHandoffError(ValueError):
    """Contrato ou registro persistido inconsistente."""


def validate_persisted_handoff(contract):
    """
    Verifica a consistencia entre:
      1. Contrato WF-04.
      2. Comprovante do adaptador persistente.
      3. Registro efetivamente existente no PostgreSQL.

    Nao realiza INSERT, UPDATE ou DELETE.

    Retorna uma copia do contrato somente apos
    a nova verificacao do registro persistido.
    """

    # ------------------------------------------------------
    # 1. VALIDAR CONTRATO ORIGINAL
    # ------------------------------------------------------

    try:
        historical, current = validate_contract(contract)
    except ValueError as exc:
        raise PersistentHandoffError(
            "Contrato WF-04 invalido para handoff persistente."
        ) from exc

    integrity = contract.get("integrity")
    handoff = contract.get("handoff")

    if not isinstance(integrity, dict):
        raise PersistentHandoffError(
            "Bloco de integridade ausente."
        )

    if not isinstance(handoff, dict):
        raise PersistentHandoffError(
            "Bloco de handoff ausente."
        )

    if (
        integrity.get("status") != "PERSISTED_VALID"
        or integrity.get("persistence_status")
        not in ("NEW_RESULT", "ALREADY_REGISTERED")
        or integrity.get("verification_method")
        != "POSTGRESQL_TRANSACTION"
        or integrity.get("verified_against_database") is not True
        or integrity.get("operational_dispatch_allowed") is not False
    ):
        raise PersistentHandoffError(
            "Comprovante inicial de persistencia invalido."
        )

    record_id = integrity.get("database_record_id")

    if type(record_id) is not int or record_id < 1:
        raise PersistentHandoffError(
            "Identificador PostgreSQL invalido."
        )

    if (
        handoff.get("source") != "WF-04"
        or handoff.get("target") != "WF-05"
        or handoff.get("status")
        != "READY_FOR_PERSISTED_MOCK_REPORT"
        or handoff.get("selected_queue_id")
        != current["queue_id"]
        or handoff.get("selected_version")
        != current["investigation_version"]
        or handoff.get("historical_queue_id")
        != historical["queue_id"]
        or handoff.get("human_review_required") is not True
        or handoff.get("operational_dispatch_allowed") is not False
        or contract.get("ready_for_operational_dispatch") is not False
    ):
        raise PersistentHandoffError(
            "Handoff nao autorizado para revisao humana."
        )

    # ------------------------------------------------------
    # 2. RECONSTRUIR E CONFERIR AS ASSINATURAS
    # ------------------------------------------------------

    current_result = copy.deepcopy(current)

    current_result.update({
        "fixture_type": "MOCK_AI_RESPONSE",
        "real_ollama_call": False,
        "ready_for_operational_dispatch": False,
    })

    record = build_integrity_record(current_result)

    verify_integrity_record(record)

    for field in (
        "content_signature",
        "analysis_signature",
        "result_key",
    ):
        if integrity.get(field) != record[field]:
            raise PersistentHandoffError(
                "Assinatura do contrato divergente: " + field
            )

    if (
        integrity.get("investigation_version")
        != current["investigation_version"]
    ):
        raise PersistentHandoffError(
            "Versao do comprovante divergente."
        )

    # ------------------------------------------------------
    # 3. CONSULTAR NOVAMENTE O POSTGRESQL
    # ------------------------------------------------------

    with connect_db() as conn:

        with conn.cursor(row_factory=tuple_row) as cur:

            cur.execute(
                """
                SELECT
                    investigation_id::text,
                    investigation_version,
                    queue_id,
                    source_event_id,
                    model_id,
                    execution_mode,
                    content_signature::text,
                    analysis_signature::text,
                    result_key::text,
                    analysis_data,
                    status,
                    operational_dispatch_allowed
                FROM public.ai_analysis_integrity
                WHERE id = %s;
                """,
                (record_id,),
            )

            saved = cur.fetchone()

    if saved is None:
        raise PersistentHandoffError(
            "Registro de integridade nao encontrado no banco."
        )

    identity = record["identity"]

    expected = (
        identity["investigation_id"],
        identity["investigation_version"],
        identity["queue_id"],
        identity["source_event_id"],
        identity["model"],
        identity["execution_mode"],
        record["content_signature"],
        record["analysis_signature"],
        record["result_key"],
        record["analysis"],
        "VALIDATED",
        False,
    )

    if saved != expected:
        raise PersistentHandoffError(
            "INTEGRITY_CONFLICT: registro PostgreSQL "
            "diverge do contrato recebido."
        )

    # ------------------------------------------------------
    # 4. LIBERAR APENAS PARA RELATORIO MOCK E REVISAO HUMANA
    # ------------------------------------------------------

    output = copy.deepcopy(contract)

    output["persistent_handoff_validation"] = {
        "status": "VALIDATED",
        "verification_method": "POSTGRESQL_ROW_RECHECK",
        "database_record_id": record_id,
        "result_key": record["result_key"],
        "analysis_signature": record["analysis_signature"],
        "human_review_required": True,
        "operational_dispatch_allowed": False,
    }

    output["ready_for_operational_dispatch"] = False

    return output
