"""
FASE 13.7.8 - Teste de persistencia PostgreSQL.

Executar os modos em processos Python independentes:
first, repeat, conflict, verify.

Utiliza somente o fixture sintetico LAB-0001.
"""

import argparse
import copy
import json
from pathlib import Path

from src.ai_engine.integrity import (
    build_integrity_record,
    verify_integrity_record,
)

from src.ai_engine.integrity_persistence import (
    IntegrityConflictError,
    persist_integrity_record,
)

from src.dedup.persistence import connect_db
from src.reports.report_builder import validate_contract


ROOT = Path(__file__).resolve().parents[1]

FIXTURE = (
    ROOT / "tests/fixtures"
    / "wf04_wf05_integrity_mock.json"
)


def load_record(modify_analysis=False):

    envelope = json.loads(
        FIXTURE.read_text(encoding="utf-8")
    )

    _, current = validate_contract(envelope)

    current = copy.deepcopy(current)

    current.update({
        "fixture_type": "MOCK_AI_RESPONSE",
        "real_ollama_call": False,
        "ready_for_operational_dispatch": False,
    })

    if modify_analysis:

        current["analysis"]["summary"] = (
            "TESTE-1378: resumo modificado "
            "para verificar conflito persistente."
        )

    record = build_integrity_record(current)

    verify_integrity_record(record)

    return record


def get_existing_rows():

    # Somente consultas de leitura.

    with connect_db() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    result_key,
                    analysis_signature,
                    content_signature,
                    operational_dispatch_allowed
                FROM public.ai_analysis_integrity
                ORDER BY id;
                """
            )

            rows = cur.fetchall()

    return rows


def fields(row):

    # Compatibilidade com tuple_row ou dict_row.

    if isinstance(row, dict):

        return (
            row["result_key"],
            row["analysis_signature"],
            row["content_signature"],
            row["operational_dispatch_allowed"],
        )

    return tuple(row)


def assert_saved(record):

    rows = get_existing_rows()

    if len(rows) != 1:
        raise AssertionError(
            "Esperado exatamente um registro "
            "na tabela de integridade. "
            f"Encontrados: {len(rows)}"
        )

    (
        result_key,
        analysis_signature,
        content_signature,
        dispatch,
    ) = fields(rows[0])

    assert result_key == record["result_key"]

    assert (
        analysis_signature
        == record["analysis_signature"]
    )

    assert (
        content_signature
        == record["content_signature"]
    )

    assert dispatch is False


def first():

    print()
    print("=== TESTE 1 - PRIMEIRA GRAVACAO ===")

    record = load_record()

    if len(get_existing_rows()) != 0:

        raise RuntimeError(
            "A tabela nao esta vazia. "
            "Nao executar novamente o primeiro teste "
            "sem investigar os registros existentes."
        )

    result = persist_integrity_record(record)

    assert result["status"] == "NEW_RESULT"

    assert result["verified_against_database"] is True

    assert result["operational_dispatch_allowed"] is False

    assert_saved(record)

    print("[OK] NEW_RESULT")
    print("[OK] Um registro persistido.")
    print("[OK] Assinaturas correspondentes.")
    print("[OK] Despacho operacional bloqueado.")


def repeat():

    print()
    print("=== TESTE 2 - REPETICAO INDEPENDENTE ===")

    record = load_record()

    result = persist_integrity_record(record)

    assert result["status"] == "ALREADY_REGISTERED"

    assert result["verified_against_database"] is True

    assert_saved(record)

    print("[OK] ALREADY_REGISTERED")
    print("[OK] Nenhuma duplicidade criada.")


def conflict():

    print()
    print("=== TESTE 3 - ANALISE DIVERGENTE ===")

    original = load_record()

    modified = load_record(modify_analysis=True)

    # A identidade logica permanece a mesma.
    # Somente a assinatura da analise muda.

    assert (
        original["result_key"]
        == modified["result_key"]
    )

    assert (
        original["content_signature"]
        == modified["content_signature"]
    )

    assert (
        original["analysis_signature"]
        != modified["analysis_signature"]
    )

    try:

        persist_integrity_record(modified)

    except IntegrityConflictError as exc:

        if "INTEGRITY_CONFLICT" not in str(exc):
            raise

        print("[OK] INTEGRITY_CONFLICT detectado.")

    else:

        raise AssertionError(
            "ERRO: analise divergente foi aceita."
        )

    # Confirmar que a tentativa nao substituiu
    # nem duplicou o resultado original.

    assert_saved(original)

    print("[OK] Analise original preservada.")
    print("[OK] Nenhuma duplicidade criada.")


def verify():

    print()
    print("=== VERIFICACAO FINAL DO POSTGRESQL ===")

    record = load_record()

    assert_saved(record)

    print("[OK] Um registro persistente.")
    print("[OK] Assinaturas originais preservadas.")
    print("[OK] Despacho operacional desabilitado.")

    print()
    print("=" * 52)
    print(" FASE 13.7.8 - VALIDACAO CONCLUIDA")
    print("=" * 52)
    print("NEW_RESULT: VALIDADO")
    print("ALREADY_REGISTERED: VALIDADO")
    print("INTEGRITY_CONFLICT: VALIDADO")
    print("PostgreSQL: PERSISTENCIA CONFIRMADA")
    print("Evento: LAB-0001 / MOCK")
    print("Ollama: NAO ACIONADO")
    print("Notificacoes: NENHUMA")
    print()
    print("[OK] TESTES DE PERSISTENCIA CONCLUIDOS")


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--mode",
        required=True,
        choices=[
            "first",
            "repeat",
            "conflict",
            "verify",
        ],
    )

    args = parser.parse_args()

    operations = {
        "first": first,
        "repeat": repeat,
        "conflict": conflict,
        "verify": verify,
    }

    operations[args.mode]()


if __name__ == "__main__":
    main()