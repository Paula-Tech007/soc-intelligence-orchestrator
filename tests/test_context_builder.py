"""
Teste do WF-03 com as versoes reais do evento LAB-0001.
Somente consultas SELECT. Nao modifica o banco.
"""

import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.context.context_builder import build_context
from src.dedup.persistence import connect_db


TABLES = (
    "investigations",
    "investigation_versions",
    "evidences",
    "event_occurrences",
    "analysis_queue",
    "audit_log",
)


def database_counts():

    counts = {}

    with connect_db() as connection:
        with connection.cursor() as cursor:

            for table in TABLES:

                cursor.execute(
                    f"SELECT COUNT(*) AS total FROM {table}"
                )

                counts[table] = cursor.fetchone()["total"]

    return counts


def run():

    before = database_counts()

    with connect_db() as connection:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    q.id,
                    q.investigation_version
                FROM analysis_queue q
                JOIN investigations i
                  ON i.id = q.investigation_id
                WHERE i.source = 'SOC-LAB'
                  AND i.source_event_id = 'LAB-0001'
                ORDER BY q.investigation_version
                """
            )

            tasks = cursor.fetchall()

    by_version = {
        item["investigation_version"]: item["id"]
        for item in tasks
    }

    assert 1 in by_version, "Versao 1 nao encontrada."
    assert 2 in by_version, "Versao 2 nao encontrada."

    version_1 = build_context(by_version[1])
    version_2 = build_context(by_version[2])

    assert version_1["requested_version"] == 1
    assert version_1["is_historical_version"] is True
    assert version_1["eligible_for_context_review"] is False
    assert version_1["context_status"] == "HISTORICAL_VERSION"
    assert version_1["event"]["severity"] == "medium"
    assert version_1["evidence_count"] == 1

    assert version_2["requested_version"] == 2
    assert version_2["current_version"] == 2
    assert version_2["is_historical_version"] is False
    assert version_2["eligible_for_context_review"] is True
    assert version_2["context_status"] == "READY_FOR_REVIEW"
    assert version_2["event"]["severity"] == "high"
    assert version_2["evidence_count"] == 2

    assert version_2["indicators"]["ips"] == [
        "192.0.2.10",
        "198.51.100.20",
    ]

    assert "lab-workstation-02" in (
        version_2["indicators"]["hostnames"]
    )

    assert version_1["ai_executed"] is False
    assert version_2["ai_executed"] is False

    after = database_counts()

    assert before == after, (
        "O teste alterou a quantidade de registros!"
    )

    print("")
    print("==========================================")
    print(" WF-03 - CONTEXTO E CORRELACAO")
    print("==========================================")
    print("")
    print(
        "[OK] Versao 1: historica | "
        "severity=medium | evidence=1"
    )
    print(
        "[OK] Versao 2: atual | "
        "severity=high | evidence=2"
    )
    print("[OK] IPs identificados corretamente.")
    print("[OK] Hostnames identificados corretamente.")
    print("[OK] Contexto respeita a versao solicitada.")
    print("[OK] Nenhuma tabela sofreu alteracoes.")
    print("[OK] Nenhuma IA foi executada.")
    print("")
    print("FASE 10.1 VALIDADA COM SUCESSO.")
    print("")


if __name__ == "__main__":
    run()
