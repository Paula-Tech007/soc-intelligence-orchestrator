"""
SOC Intelligence Orchestrator
FASE 13.9.4.2 - Persistent Report Integration

Integra a verificacao PostgreSQL do WF-05 com o
gerador HTML original.

Ambiente: LAB
Execucao: MOCK
Despacho operacional: PROIBIDO
"""

from src.reports.persistent_handoff import (
    validate_persisted_handoff,
)

from src.reports.report_builder import (
    build_report,
)


class PersistentReportError(ValueError):
    """Falha na preparacao do relatorio persistente."""


def build_persisted_report(contract):
    """
    Recebe um contrato persistente WF-04.

    Ordem obrigatoria:
      1. Validar novamente contra PostgreSQL.
      2. Confirmar revisao humana obrigatoria.
      3. Gerar HTML somente apos o gate aprovado.
      4. Devolver pacote LAB/MOCK.

    Nunca executa despacho operacional.
    """

    # ------------------------------------------------------
    # 1. GATE DE INTEGRIDADE POSTGRESQL
    # ------------------------------------------------------

    validated = validate_persisted_handoff(contract)

    validation = validated.get(
        "persistent_handoff_validation"
    )

    if not isinstance(validation, dict):
        raise PersistentReportError(
            "Validacao persistente ausente."
        )

    if (
        validation.get("status") != "VALIDATED"
        or validation.get("verification_method")
        != "POSTGRESQL_ROW_RECHECK"
        or validation.get("human_review_required") is not True
        or validation.get("operational_dispatch_allowed") is not False
    ):
        raise PersistentReportError(
            "Gate nao autorizou a geracao do relatorio."
        )

    record_id = validation.get("database_record_id")

    if type(record_id) is not int or record_id < 1:
        raise PersistentReportError(
            "Registro PostgreSQL invalido."
        )

    # ------------------------------------------------------
    # 2. GERAR HTML SOMENTE APOS VALIDACAO
    # ------------------------------------------------------

    html = build_report(validated)

    if (
        not isinstance(html, str)
        or not html.strip()
    ):
        raise PersistentReportError(
            "Gerador HTML retornou conteudo invalido."
        )

    # ------------------------------------------------------
    # 3. PREPARAR SAIDA PARA REVISAO HUMANA
    # ------------------------------------------------------

    return {
        "schema_version": "1.0",
        "environment": "LAB",
        "processor": "WF-05",
        "integration_mode": "PERSISTED_MOCK",
        "report_status": "AWAITING_HUMAN_REVIEW",
        "database_record_id": record_id,
        "result_key": validation["result_key"],
        "analysis_signature": validation["analysis_signature"],
        "verification_method": "POSTGRESQL_ROW_RECHECK",
        "persistent_handoff_validated": True,
        "human_review_required": True,
        "operational_dispatch_allowed": False,
        "notification_sent": False,
        "html": html,
    }
