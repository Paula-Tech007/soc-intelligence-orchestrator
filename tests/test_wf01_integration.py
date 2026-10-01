"""
SOC INTELLIGENCE ORCHESTRATOR
FASE 08.1

Valida o contrato JSON do WF-01 com o modulo
Python de persistencia do WF-02.

Somente dados sinteticos.
Nao acessa n8n remoto ou sistemas corporativos.
"""

import copy
import sys
import uuid

from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.dedup.persistence import process_event, connect_db


def main():

    identificador = uuid.uuid4().hex[:12]

    collection_id = f"LAB-INTEGRATION-{identificador}"
    event_id = f"LAB-INT-{identificador}"

    agora = datetime.now(timezone.utc).isoformat()

    # Estrutura de transporte produzida pelo WF-01.

    original = {
        "schema_version": "1.0",
        "environment": "LAB",
        "collection_id": collection_id,
        "collection_sequence": 1,
        "source": "SOC-LAB",
        "collected_at": agora,
        "ingested_at": agora,
        "raw_event": {
            "sample_case": "NEW_EVENT",
            "source_event_id": event_id,
            "occurred_at": agora,
            "event_type": "suspicious_connection",
            "severity": "medium",
            "entity": {
                "hostname": "lab-workstation-01",
                "src_ip": "192.0.2.10",
                "dst_ip": "198.51.100.20"
            },
            "evidence": [{
                "evidence_id": "LAB-EV-001",
                "type": "network_connection",
                "src_ip": "192.0.2.10",
                "dst_ip": "198.51.100.20",
                "dst_port": 443
            }]
        },
        "validation": {
            "status": "VALID",
            "errors": []
        },
        "collector": "WF-01",
        "target_workflow": "WF-02",
        "dispatch_status": "MOCK_ONLY",
        "real_execution_started": False
    }

    # Segunda mensagem: repeticao do mesmo evento.

    repetido = copy.deepcopy(original)

    repetido["collection_sequence"] = 2
    repetido["raw_event"]["sample_case"] = "EXACT_REPEAT"

    # Terceira mensagem: nova evidencia e severidade.

    atualizado = copy.deepcopy(original)

    atualizado["collection_sequence"] = 3
    atualizado["raw_event"]["sample_case"] = "MATERIAL_UPDATE"
    atualizado["raw_event"]["severity"] = "high"

    atualizado["raw_event"]["entity"]["related_hostnames"] = [
        "lab-workstation-02"
    ]

    atualizado["raw_event"]["evidence"].append({
        "evidence_id": "LAB-EV-002",
        "type": "host_observation",
        "hostname": "lab-workstation-02"
    })

    casos = [
        (original, "NEW_EVENT", True),
        (repetido, "EXACT_REPEAT", False),
        (atualizado, "MATERIAL_UPDATE", True),
    ]

    print("")
    print("========================================")
    print(" INTEGRACAO WF-01 -> PYTHON -> POSTGRES")
    print("========================================")

    resultados = []

    for indice, (payload, esperado, analisar) in enumerate(
        casos,
        start=1
    ):

        resultado = process_event(payload)

        assert resultado["status"] == esperado, (
            f"Teste {indice}: esperado {esperado}, "
            f"recebido {resultado['status']}"
        )

        assert resultado["should_analyze"] is analisar

        assert resultado["persistence"] == "POSTGRESQL"

        resultados.append(resultado)

        print(f"[OK] Evento {indice}: {resultado['status']}")

    # Conferir o historico diretamente no PostgreSQL.

    investigation_id = resultados[0]["investigation_id"]

    with connect_db() as conexao:

        with conexao.cursor() as cursor:

            cursor.execute(
                """
                SELECT investigation_version, occurrence_count
                FROM investigations
                WHERE id = %s
                """,
                (investigation_id,)
            )

            registro = cursor.fetchone()

            assert registro["investigation_version"] == 2
            assert registro["occurrence_count"] == 3

            cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM analysis_queue
                WHERE investigation_id = %s
                """,
                (investigation_id,)
            )

            assert cursor.fetchone()["total"] == 2

    print("")
    print("[OK] Contrato WF-01 compativel.")
    print("[OK] Historico persistido.")
    print("[OK] Versoes: 2.")
    print("[OK] Ocorrencias: 3.")
    print("[OK] Tarefas de analise: 2.")
    print("")
    print("FASE 08.1 VALIDADA COM SUCESSO.")


if __name__ == "__main__":
    main()