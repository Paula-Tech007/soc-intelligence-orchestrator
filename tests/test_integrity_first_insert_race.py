"""
FASE 13.7.11 - Concorrencia na primeira insercao.

Usa o LAB-0001, mas com um model_id exclusivo
para este teste. Preserva o registro original.

--preflight: somente leitura
--worker: processo concorrente
--race: executa dois workers simultaneamente
"""

import argparse
import copy
import json
import os
import subprocess
import sys

from pathlib import Path

from psycopg.rows import tuple_row

from src.ai_engine.integrity import (
    build_integrity_record,
    verify_integrity_record,
)

from src.ai_engine.integrity_persistence import (
    persist_integrity_record,
)

from src.dedup.persistence import connect_db

from src.reports.report_builder import validate_contract


ROOT = Path(__file__).resolve().parents[1]

FIXTURE = (
    ROOT / "tests/fixtures"
    / "wf04_wf05_integrity_mock.json"
)

RACE_MODEL = "qwen3:4b-instruct-race-mock-13711"


def make_records():

    envelope = json.loads(
        FIXTURE.read_text(encoding="utf-8-sig")
    )

    _, current = validate_contract(envelope)

    original = copy.deepcopy(current)

    original.update({
        "fixture_type": "MOCK_AI_RESPONSE",
        "real_ollama_call": False,
        "ready_for_operational_dispatch": False,
    })

    original_record = build_integrity_record(original)

    variant = copy.deepcopy(original)

    # Mudar exclusivamente a identidade do modelo MOCK.
    # A investigacao, a versao e o contexto permanecem iguais.

    variant["model"] = RACE_MODEL

    race_record = build_integrity_record(variant)

    verify_integrity_record(original_record)
    verify_integrity_record(race_record)

    assert (
        original_record["result_key"]
        != race_record["result_key"]
    )

    assert (
        original_record["content_signature"]
        == race_record["content_signature"]
    )

    assert (
        original_record["analysis_signature"]
        == race_record["analysis_signature"]
    )

    return original_record, race_record


def database_rows():

    with connect_db() as conn:

        with conn.cursor(row_factory=tuple_row) as cur:

            cur.execute("""
                SELECT
                    id,
                    model_id,
                    result_key::text,
                    analysis_signature::text,
                    content_signature::text,
                    operational_dispatch_allowed

                FROM public.ai_analysis_integrity
                ORDER BY id;
            """)

            return cur.fetchall()


def verify_state(expect_new):

    original, race = make_records()

    rows = database_rows()

    original_rows = [
        row for row in rows
        if row[2] == original["result_key"]
    ]

    race_rows = [
        row for row in rows
        if row[2] == race["result_key"]
    ]

    assert len(original_rows) == 1, (
        "Registro LAB-0001 original ausente ou duplicado."
    )

    saved = original_rows[0]

    assert saved[0] == 1
    assert saved[3] == original["analysis_signature"]
    assert saved[4] == original["content_signature"]
    assert saved[5] is False

    expected_count = 2 if expect_new else 1

    assert len(rows) == expected_count, (
        f"Quantidade inesperada: {len(rows)}. "
        f"Esperado: {expected_count}."
    )

    if expect_new:

        assert len(race_rows) == 1, (
            "Esperado um unico registro concorrente."
        )

        new = race_rows[0]

        assert new[1] == RACE_MODEL
        assert new[3] == race["analysis_signature"]
        assert new[4] == race["content_signature"]
        assert new[5] is False

    else:

        assert len(race_rows) == 0, (
            "A identidade do teste concorrente ja existe. "
            "Nao iniciar novamente."
        )

    return rows


def preflight():

    print()
    print("=== FASE 13.7.11 - PREFLIGHT ===")

    rows = verify_state(expect_new=False)

    print("[OK] Registro original preservado.")
    print("[OK] Identidade concorrente ainda inexistente.")
    print("[OK] Assinaturas verificadas.")
    print("[OK] Despacho operacional desabilitado.")
    print("Registros atuais:", len(rows))
    print("Consultas: SOMENTE SELECT")
    print()
    print("[OK] PREFLIGHT 13.7.11 APROVADO")


def worker():

    _, race_record = make_records()

    # Aguardar sinal do processo principal.
    # Os dois workers serao liberados juntos.

    print("READY", flush=True)

    command = sys.stdin.readline().strip()

    if command != "GO":
        raise RuntimeError("Worker nao autorizado.")

    result = persist_integrity_record(race_record)

    print(
        json.dumps({
            "status": result["status"],
            "record_id": result["record_id"],
            "result_key": result["result_key"],
        }),
        flush=True,
    )


def race():

    verify_state(expect_new=False)

    print()
    print("=== INICIAR DOIS PROCESSOS INDEPENDENTES ===")

    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
    ]

    processes = []

    try:

        for _ in range(2):

            process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
                env=os.environ.copy(),
            )

            processes.append(process)

        for index, process in enumerate(processes, 1):

            ready = process.stdout.readline().strip()

            if ready != "READY":
                raise RuntimeError(
                    f"Worker {index} nao ficou pronto."
                )

            print(
                f"[OK] Worker {index} pronto.",
                flush=True,
            )

        # Disparar as duas tentativas de insercao.

        for process in processes:

            process.stdin.write("GO\n")
            process.stdin.flush()

        for process in processes:

            process.stdin.close()
            process.stdin = None

        results = []

        for index, process in enumerate(processes, 1):

            stdout, stderr = process.communicate(
                timeout=45
            )

            if process.returncode != 0:
                print(stderr)
                raise RuntimeError(
                    f"Worker {index} falhou."
                )

            result = json.loads(stdout.strip())

            results.append(result)

            print(
                f"Worker {index}: {result['status']}"
            )

        statuses = sorted(
            result["status"] for result in results
        )

        assert statuses == [
            "ALREADY_REGISTERED",
            "NEW_RESULT",
        ], f"Resultados inesperados: {statuses}"

        assert (
            results[0]["record_id"]
            == results[1]["record_id"]
        )

        rows = verify_state(expect_new=True)

        print()
        print("=" * 52)
        print(" FASE 13.7.11 - CONCORRENCIA APROVADA")
        print("=" * 52)
        print("NEW_RESULT: 1")
        print("ALREADY_REGISTERED: 1")
        print("INTEGRITY_CONFLICT: 0")
        print("Total de registros:", len(rows))
        print("Registro original: PRESERVADO")
        print("Duplicidade concorrente: NENHUMA")
        print("Ollama: NAO ACIONADO")
        print("Notificacoes: NENHUMA")
        print()
        print("[OK] PRIMEIRA INSERCAO CONCORRENTE VALIDADA")

    finally:

        for process in processes:

            if process.poll() is None:
                process.kill()
                process.wait()


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--preflight",
        action="store_true",
    )

    parser.add_argument(
        "--worker",
        action="store_true",
    )

    parser.add_argument(
        "--race",
        action="store_true",
    )

    args = parser.parse_args()

    if sum([
        args.preflight,
        args.worker,
        args.race,
    ]) != 1:

        parser.error("Selecione exatamente um modo.")

    if args.preflight:
        preflight()

    elif args.worker:
        worker()

    elif args.race:
        race()
