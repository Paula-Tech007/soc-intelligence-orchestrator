"""
Persistencia dos resultados de integridade do WF-04.

Escopo: ambiente LAB / MOCK.

Reutiliza a conexao PostgreSQL existente no projeto.

Comportamentos:
- NEW_RESULT
- ALREADY_REGISTERED
- INTEGRITY_CONFLICT

Nenhum resultado e automaticamente encaminhado para operacao.
"""

from psycopg.types.json import Jsonb
from psycopg.rows import tuple_row

from src.ai_engine.integrity import verify_integrity_record
from src.dedup.persistence import connect_db


class IntegrityConflictError(ValueError):
    """Identidade existente com dados de integridade divergentes."""


def _validate_record(record):
    """Verifica o contrato recebido antes de acessar o banco."""

    if not isinstance(record, dict):
        raise ValueError("Registro de integridade invalido.")

    verify_integrity_record(record)

    identity = record["identity"]

    if identity["environment"] != "LAB":
        raise ValueError("Somente ambiente LAB e permitido.")

    if identity["execution_mode"] != "MOCK_AI_RESPONSE":
        raise ValueError("Somente MOCK_AI_RESPONSE e permitido.")

    if record["verified_against_database"] is not False:
        raise ValueError("Estado inicial de verificacao invalido.")

    if record["operational_dispatch_allowed"] is not False:
        raise ValueError("Despacho operacional nao permitido.")

    return identity


def _database_identity(conn, identity):
    """
    Confirma que fila, versao e assinatura pertencem
    a mesma investigacao persistida.
    """

    with conn.cursor(row_factory=tuple_row) as cur:

        cur.execute(
            """
            SELECT q.id
            FROM public.analysis_queue AS q

            JOIN public.investigation_versions AS v
              ON v.investigation_id = q.investigation_id
             AND v.version_number = q.investigation_version

            JOIN public.investigations AS i
              ON i.id = q.investigation_id

            WHERE q.id = %s

              AND q.investigation_id = %s::uuid

              AND q.investigation_version = %s

              AND v.content_signature = %s

              AND i.source_event_id = %s

            FOR SHARE OF q, v, i
            """,
            (
                identity["queue_id"],
                identity["investigation_id"],
                identity["investigation_version"],
                identity["content_signature"],
                identity["source_event_id"],
            ),
        )

        found = cur.fetchone()

    if found is None:
        raise IntegrityConflictError(
            "INTEGRITY_CONFLICT: identidade nao "
            "corresponde a fila/versao/assinatura "
            "registrada no PostgreSQL."
        )


def _find_existing(conn, identity, record):
    """
    Procura conflitos por result_key OU por identidade
    logica. Tambem cobre concorrencia entre processos.
    """

    with conn.cursor(row_factory=tuple_row) as cur:

        cur.execute(
            """
            SELECT
                id,
                investigation_id::text,
                investigation_version,
                queue_id,
                source_event_id,
                model_id,
                execution_mode,
                content_signature,
                analysis_signature,
                result_key,
                analysis_data,
                status,
                operational_dispatch_allowed

            FROM public.ai_analysis_integrity

            WHERE result_key = %s

               OR (
                    investigation_id = %s::uuid
                AND investigation_version = %s
                AND model_id = %s
                AND execution_mode = %s
               )
            """,
            (
                record["result_key"],
                identity["investigation_id"],
                identity["investigation_version"],
                identity["model"],
                identity["execution_mode"],
            ),
        )

        return cur.fetchall()


def _same_record(existing, identity, record):
    """Compara tambem o JSON, nao apenas as assinaturas."""

    (
        row_id,
        investigation_id,
        version,
        queue_id,
        source_event_id,
        model_id,
        execution_mode,
        content_signature,
        analysis_signature,
        result_key,
        analysis_data,
        status,
        operational_dispatch_allowed,
    ) = existing

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

    actual = (
        investigation_id,
        version,
        queue_id,
        source_event_id,
        model_id,
        execution_mode,
        content_signature,
        analysis_signature,
        result_key,
        analysis_data,
        status,
        operational_dispatch_allowed,
    )

    return actual == expected


def persist_integrity_record(record):
    """
    Registra uma analise validada no PostgreSQL.

    NEW_RESULT:
        primeira insercao.

    ALREADY_REGISTERED:
        registro completamente identico.

    INTEGRITY_CONFLICT:
        mesma identidade logica ou result_key
        com dados divergentes.

    Utiliza INSERT ... ON CONFLICT DO NOTHING
    e as UNIQUE constraints da migracao 002.
    """

    identity = _validate_record(record)

    with connect_db() as conn:

        with conn.transaction():

            # A verificacao ocorre dentro da mesma transacao.
            _database_identity(conn, identity)

            with conn.cursor(row_factory=tuple_row) as cur:

                cur.execute(
                    """
                    INSERT INTO public.ai_analysis_integrity
                    (
                        investigation_id,
                        investigation_version,
                        queue_id,
                        source_event_id,
                        model_id,
                        execution_mode,
                        content_signature,
                        analysis_signature,
                        result_key,
                        analysis_data,
                        status,
                        operational_dispatch_allowed
                    )
                    VALUES
                    (
                        %s::uuid,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        'VALIDATED',
                        FALSE
                    )

                    ON CONFLICT DO NOTHING

                    RETURNING id
                    """,
                    (
                        identity["investigation_id"],
                        identity["investigation_version"],
                        identity["queue_id"],
                        identity["source_event_id"],
                        identity["model"],
                        identity["execution_mode"],
                        record["content_signature"],
                        record["analysis_signature"],
                        record["result_key"],
                        Jsonb(record["analysis"]),
                    ),
                )

                inserted = cur.fetchone()

            if inserted is not None:

                return {
                    "status": "NEW_RESULT",
                    "record_id": inserted[0],
                    "result_key": record["result_key"],
                    "analysis_signature": record["analysis_signature"],
                    "verified_against_database": True,
                    "operational_dispatch_allowed": False,
                }

            # Uma UNIQUE constraint encontrou um registro.
            # Comparar todo o contrato antes de consider?-lo
            # uma repeticao idempotente.

            existing_rows = _find_existing(
                conn,
                identity,
                record,
            )

            if (
                len(existing_rows) == 1
                and _same_record(
                    existing_rows[0],
                    identity,
                    record,
                )
            ):

                return {
                    "status": "ALREADY_REGISTERED",
                    "record_id": existing_rows[0][0],
                    "result_key": record["result_key"],
                    "analysis_signature": record["analysis_signature"],
                    "verified_against_database": True,
                    "operational_dispatch_allowed": False,
                }

            raise IntegrityConflictError(
                "INTEGRITY_CONFLICT: resultado persistido "
                "diverge do contrato recebido."
            )
