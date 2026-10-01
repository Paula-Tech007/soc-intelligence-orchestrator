"""
FASE 11.5.1 - Exportar contrato do WF-04.

Utiliza modelo simulado.
Nao acessa PostgreSQL.
Nao acessa Ollama.
Nao atualiza a fila de analise.
"""

import json
import sys

from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT))

from src.ai_engine.engine import analyze

from test_ai_engine_live import prepare_context


class FakeModel:

    def __init__(self):
        self.calls = 0

    def invoke(self, messages):

        self.calls += 1

        return SimpleNamespace(
            content=json.dumps({
                "summary": (
                    "Evento sintetico LAB-0001 "
                    "encaminhado para revisao humana."
                ),
                "assessment": (
                    "Existem duas evidencias registradas. "
                    "As correlacoes sao informativas e "
                    "nao comprovam um mesmo incidente."
                ),
                "evidence_ids": [
                    "LAB-EV-001",
                    "LAB-EV-002"
                ],
                "limitations": [
                    "Dados exclusivamente sinteticos.",
                    "Sem comprovacao de atividade maliciosa."
                ],
                "review_actions": [
                    "Revisar as evidencias do evento."
                ]
            }, ensure_ascii=False)
        )


def main():

    fixture = (
        ROOT / "tests" / "fixtures"
        / "wf03_context_snapshot.json"
    )

    snapshots = json.loads(
        fixture.read_text(encoding="utf-8")
    )

    versions = {
        item["requested_version"]: item
        for item in snapshots
    }

    if set(versions) != {1, 2}:
        raise RuntimeError(
            "Snapshot inesperado: requer versoes 1 e 2."
        )

    model = FakeModel()

    historical = analyze(
        prepare_context(versions[1]),
        model=model
    )

    current = analyze(
        prepare_context(versions[2]),
        model=model
    )

    assert historical["status"] == "SKIPPED"

    assert historical["ai_executed"] is False

    assert current["status"] == "ANALYSIS_COMPLETED"

    assert current["requires_human_review"] is True

    assert set(current["analysis"]["evidence_ids"]) == {
        "LAB-EV-001",
        "LAB-EV-002"
    }

    # Somente a versao atual pode ser encaminhada.

    assert model.calls == 1, (
        "Quantidade inesperada de chamadas simuladas."
    )

    output = {
        "schema_version": "1.0",
        "environment": "LAB",
        "origin": "WF-04",
        "fixture_type": "MOCK_AI_RESPONSE",
        "real_ollama_call": False,
        "ready_for_operational_dispatch": False,
        "results": [
            historical,
            current
        ]
    }

    destination = (
        ROOT / "tests" / "fixtures"
        / "wf04_output_mock.json"
    )

    if destination.exists():
        raise RuntimeError(
            "Contrato de saida ja existe. "
            "Nao sera sobrescrito automaticamente."
        )

    destination.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2
        ) + "\n",
        encoding="utf-8"
    )

    # Verificar a leitura do arquivo gravado.

    saved = json.loads(
        destination.read_text(encoding="utf-8")
    )

    assert len(saved["results"]) == 2

    assert saved["results"][0]["status"] == "SKIPPED"

    assert (
        saved["results"][1]["status"]
        == "ANALYSIS_COMPLETED"
    )

    print("")
    print("========================================")
    print(" FASE 11.5.1 - CONTRATO WF-04")
    print("========================================")
    print(f"Arquivo: {destination}")
    print("Versao 1: SKIPPED")
    print("Versao 2: ANALYSIS_COMPLETED")
    print("Chamadas simuladas: 1")
    print("Chamadas reais ao Ollama: 0")
    print("Gravacoes no PostgreSQL: 0")
    print("Resultado: JSON valido")
    print("")
    print("[OK] CONTRATO DE SAIDA GERADO")


if __name__ == "__main__":
    main()
