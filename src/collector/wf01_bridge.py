"""
SOC Intelligence Orchestrator - WF-01 Bridge.

Recebe um lote JSON do coletor e utiliza o modulo de
persistencia local do WF-02.

Somente LAB. Nao disponibiliza endpoint de rede.
"""

import json
import sys

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(ROOT))

from src.dedup.persistence import process_event


MAX_FILE_SIZE = 2 * 1024 * 1024


def validate_batch(batch):

    if not isinstance(batch, list) or not batch:
        raise ValueError(
            "A entrada deve ser uma lista JSON nao vazia."
        )

    for index, item in enumerate(batch, start=1):

        if not isinstance(item, dict):
            raise ValueError(
                f"Item {index}: registro invalido."
            )

        checks = {
            "schema_version": item.get("schema_version") == "1.0",
            "environment": item.get("environment") == "LAB",
            "source": item.get("source") == "SOC-LAB",
            "collector": item.get("collector") == "WF-01",
            "target_workflow": item.get("target_workflow") == "WF-02",
            "validation": item.get("validation", {}).get("status") == "VALID",
            "dispatch_status": item.get("dispatch_status") == "MOCK_ONLY",
            "real_execution_started": item.get("real_execution_started") is False,
            "collection_id": bool(item.get("collection_id")),
            "collection_sequence": (
                type(item.get("collection_sequence")) is int
                and item["collection_sequence"] > 0
            ),
            "raw_event": isinstance(item.get("raw_event"), dict),
        }

        invalid = [
            key
            for key, passed in checks.items()
            if not passed
        ]

        if invalid:
            raise ValueError(
                f"Item {index}: contrato invalido: "
                + ", ".join(invalid)
            )

    return batch


def main():

    if len(sys.argv) != 2:
        raise SystemExit(
            "Uso: python src/collector/wf01_bridge.py "
            "tests/fixtures/wf01_batch_lab.json"
        )

    path = Path(sys.argv[1]).resolve()

    if not path.is_file():
        raise FileNotFoundError(path)

    if path.stat().st_size > MAX_FILE_SIZE:
        raise ValueError("Lote excede 2 MB.")

    batch = json.loads(
        path.read_text(encoding="utf-8")
    )

    # Validar o contrato de todos os itens ANTES
    # de iniciar o processamento do lote.
    validate_batch(batch)

    print("")
    print("========================================")
    print(" WF-01 -> PYTHON -> POSTGRESQL")
    print("========================================")
    print(f"Eventos recebidos: {len(batch)}")
    print("")

    results = []

    for index, item in enumerate(batch, start=1):

        result = process_event(item)

        results.append(result)

        print(
            f"[{index}] {result['status']} | "
            f"should_analyze={result['should_analyze']}"
        )

    eligible = sum(
        item["should_analyze"]
        for item in results
    )

    print("")
    print(f"Eventos processados: {len(results)}")
    print(f"Elegiveis para analise: {eligible}")
    print("Persistencia: POSTGRESQL")
    print("IA executada: NAO")
    print("Notificacoes enviadas: NAO")
    print("")
    print("[OK] INTEGRACAO LOCAL CONCLUIDA")


if __name__ == "__main__":
    main()
