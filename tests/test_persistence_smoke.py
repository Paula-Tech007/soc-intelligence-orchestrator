"""
Teste funcional de persistencia entre processos independentes.

Utiliza somente dados sinteticos e cria uma identidade LAB
exclusiva a cada execucao.

Nao executa IA, notificacoes ou integracoes corporativas.
"""

import copy
import json
import subprocess
import sys
import uuid

from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT))


def processar_em_outro_processo(payload):

    resultado = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            json.dumps(payload),
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
        timeout=30,
    )

    return json.loads(resultado.stdout)


def executar_testes():

    from src.dedup.persistence import connect_db

    identificador = uuid.uuid4().hex[:12]

    source_event_id = f"LAB-PERSIST-{identificador}"

    collection_id = f"LAB-COLLECTION-{identificador}"

    agora = datetime.now(timezone.utc).isoformat()

    evidencia_original = {
        "evidence_id": "LAB-EV-001",
        "type": "network_connection",
        "src_ip": "192.0.2.10",
        "dst_ip": "198.51.100.20",
        "dst_port": 443,
    }

    evento_original = {
        "source_event_id": source_event_id,
        "occurred_at": agora,
        "event_type": "suspicious_connection",
        "severity": "medium",
        "entity": {
            "hostname": "lab-workstation-01",
            "src_ip": "192.0.2.10",
            "dst_ip": "198.51.100.20",
        },
        "evidence": [evidencia_original],
    }

    evento_atualizado = copy.deepcopy(evento_original)

    evento_atualizado["severity"] = "high"

    evento_atualizado["entity"]["related_hostnames"] = [
        "lab-workstation-02"
    ]

    evento_atualizado["evidence"].append({
        "evidence_id": "LAB-EV-002",
        "type": "host_observation",
        "hostname": "lab-workstation-02",
    })

    def montar_payload(evento, colecao, sequencia):

        return {
            "schema_version": "1.0",
            "environment": "LAB",
            "source": "SOC-LAB",
            "collection_id": colecao,
            "collection_sequence": sequencia,
            "ingested_at": agora,
            "raw_event": copy.deepcopy(evento),
        }

    payloads = [
        montar_payload(
            evento_original,
            collection_id,
            1,
        ),
        montar_payload(
            evento_original,
            collection_id,
            2,
        ),
        montar_payload(
            evento_atualizado,
            collection_id,
            3,
        ),
        montar_payload(
            evento_atualizado,
            collection_id,
            3,
        ),
        montar_payload(
            evento_original,
            collection_id + "-RECHECK",
            1,
        ),
    ]

    esperados = [
        ("NEW_EVENT", True),
        ("EXACT_REPEAT", False),
        ("MATERIAL_UPDATE", True),
        ("ALREADY_PROCESSED", False),
        ("EXACT_REPEAT", False),
    ]

    print("")
    print("==========================================")
    print(" TESTE DE PERSISTENCIA - SOC LAB")
    print("==========================================")
    print(f"Evento sintetico: {source_event_id}")
    print("")

    resultados = []

    for indice, (payload, esperado) in enumerate(
        zip(payloads, esperados),
        start=1,
    ):

        # Cada chamada inicia um novo processo Python.
        resultado = processar_em_outro_processo(payload)

        status_esperado, analise_esperada = esperado

        assert resultado["status"] == status_esperado, (
            f"Teste {indice}: classificacao incorreta. "
            f"Recebido: {resultado['status']}"
        )

        assert (
            resultado["should_analyze"]
            is analise_esperada
        ), f"Teste {indice}: decisao incorreta."

        assert resultado["persistence"] == "POSTGRESQL"

        resultados.append(resultado)

        print(
            f"[OK] Teste {indice}: "
            f"{resultado['status']} | "
            f"should_analyze={resultado['should_analyze']}"
        )

    # ======================================================
    # CONFERENCIA DIRETA NO POSTGRESQL
    # ======================================================

    with connect_db() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    investigation_version,
                    occurrence_count
                FROM investigations
                WHERE source = %s
                  AND source_event_id = %s
                  AND event_type = %s
                """,
                (
                    "SOC-LAB",
                    source_event_id,
                    "suspicious_connection",
                ),
            )

            investigation = cursor.fetchone()

            assert investigation is not None, (
                "Investigacao nao encontrada."
            )

            investigation_id = investigation["id"]

            assert investigation["investigation_version"] == 2

            assert investigation["occurrence_count"] == 4

            contagens = {}

            tabelas = (
                "investigation_versions",
                "event_occurrences",
                "evidences",
                "analysis_queue",
                "audit_log",
            )

            for tabela in tabelas:

                # Os nomes das tabelas sao constantes internas,
                # nunca recebidas de entrada externa.

                cursor.execute(
                    f"""
                    SELECT COUNT(*) AS total
                    FROM {tabela}
                    WHERE investigation_id = %s
                    """,
                    (investigation_id,),
                )

                contagens[tabela] = cursor.fetchone()["total"]

            esperadas = {
                "investigation_versions": 2,
                "event_occurrences": 4,
                "evidences": 2,
                "analysis_queue": 2,
                "audit_log": 4,
            }

            assert contagens == esperadas, (
                "Contagens inesperadas no PostgreSQL: "
                f"{contagens}"
            )

    # ======================================================
    # RESULTADO FINAL
    # ======================================================

    print("")
    print("=== CONFERENCIA DO POSTGRESQL ===")

    print("Investigation version: 2")
    print("Occurrence count: 4")

    for tabela, quantidade in contagens.items():
        print(f"{tabela}: {quantidade}")

    print("")
    print("==========================================")
    print(" TODOS OS TESTES PASSARAM")
    print(" PERSISTENCIA ENTRE PROCESSOS: OK")
    print(" DEDUPLICACAO: OK")
    print(" VERSIONAMENTO: OK")
    print(" AUDITORIA: OK")
    print("==========================================")


if __name__ == "__main__":

    if len(sys.argv) > 1 and sys.argv[1] == "--worker":

        from src.dedup.persistence import process_event

        if len(sys.argv) != 3:
            raise SystemExit("Payload obrigatorio.")

        payload = json.loads(sys.argv[2])

        resultado = process_event(payload)

        print(json.dumps(resultado))

    else:

        executar_testes()