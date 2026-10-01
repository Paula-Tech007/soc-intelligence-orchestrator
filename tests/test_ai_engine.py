"""
WF-04 - Testes offline do motor.

Nao acessa Ollama, banco ou rede.
Usa uma resposta simulada para verificar os contratos.
"""

import copy
import json
import sys

from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT))

from src.ai_engine.engine import analyze


class FakeModel:

    def __init__(self, content):

        self.content = content
        self.calls = 0

    def invoke(self, messages):

        self.calls += 1

        assert len(messages) == 2

        return SimpleNamespace(
            content=self.content
        )


def make_context(snapshot):

    # Reproduz a estrutura do ultimo Code node
    # do WF-03 ja corrigido.

    eligible = snapshot["eligible_for_context_review"]

    return {
        "schema_version": "1.0",
        "environment": "LAB",
        "processor": "WF-03",
        "queue_id": snapshot["queue_id"],
        "investigation_id": snapshot["investigation_id"],
        "source_event_id": snapshot["source_event_id"],
        "requested_version": snapshot["requested_version"],
        "current_version": snapshot["current_version"],
        "context_status": snapshot["context_status"],
        "is_historical_version": snapshot[
            "is_historical_version"
        ],
        "event": snapshot["event"],
        "changed_fields": snapshot["changed_fields"],
        "evidence_count": snapshot["evidence_count"],
        "indicators": snapshot["indicators"],
        "correlations": snapshot["correlations"],
        "provenance": snapshot["provenance"],
        "decision": {
            "eligible_for_ai": eligible,
            "target_workflow": "WF-04" if eligible else None,
        },
        "validation_status": "VALID",
        "dispatch_status": "MOCK_ONLY",
        "real_execution_started": False,
        "ai_executed": False,
        "notification_sent": False,
    }


def assert_rejected(context, model):

    try:
        analyze(context, model=model)

    except ValueError:
        pass

    else:
        raise AssertionError(
            "Contexto invalido nao foi bloqueado."
        )


def main():

    snapshot_path = (
        ROOT / "tests" / "fixtures"
        / "wf03_context_snapshot.json"
    )

    snapshots = json.loads(
        snapshot_path.read_text(encoding="utf-8")
    )

    by_version = {
        item["requested_version"]: item
        for item in snapshots
    }

    historical = make_context(by_version[1])

    current = make_context(by_version[2])

    valid_response = json.dumps({
        "summary": "Evento LAB com duas evidencias.",
        "assessment": (
            "Dados justificam revisao humana; "
            "nao comprovam comprometimento."
        ),
        "evidence_ids": [
            "LAB-EV-001",
            "LAB-EV-002",
        ],
        "limitations": [
            "Dados sinteticos.",
        ],
        "review_actions": [
            "Revisar as evidencias registradas.",
        ],
    })

    fake = FakeModel(valid_response)

    # TESTE 1 - BLOQUEAR VERSAO HISTORICA

    result = analyze(historical, model=fake)

    assert result["status"] == "SKIPPED"
    assert result["ai_executed"] is False
    assert fake.calls == 0

    print("[OK] Historico bloqueado sem chamar IA.")

    # TESTE 2 - ANALISAR VERSAO ATUAL

    result = analyze(current, model=fake)

    assert result["status"] == "ANALYSIS_COMPLETED"
    assert result["requires_human_review"] is True
    assert fake.calls == 1

    assert result["analysis"]["evidence_ids"] == [
        "LAB-EV-001",
        "LAB-EV-002",
    ]

    print("[OK] Versao atual gerou analise estruturada.")

    # TESTE 3 - BLOQUEAR AMBIENTE DIFERENTE

    invalid = copy.deepcopy(current)

    invalid["environment"] = "PROD"

    assert_rejected(invalid, fake)

    assert fake.calls == 1

    print("[OK] Ambiente fora de LAB bloqueado.")

    # TESTE 4 - BLOQUEAR DECISAO INCONSISTENTE

    invalid = copy.deepcopy(historical)

    invalid["decision"]["eligible_for_ai"] = True
    invalid["decision"]["target_workflow"] = "WF-04"

    assert_rejected(invalid, fake)

    assert fake.calls == 1

    print("[OK] Elegibilidade inconsistente bloqueada.")

    # TESTE 5 - BLOQUEAR EVIDENCIA INVENTADA

    invented = FakeModel(json.dumps({
        "summary": "Teste LAB.",
        "assessment": "Revisao necessaria.",
        "evidence_ids": ["LAB-EV-999"],
        "limitations": [],
        "review_actions": [],
    }))

    assert_rejected(current, invented)

    assert invented.calls == 1

    print("[OK] Evidencia inexistente rejeitada.")

    # TESTE 6 - BLOQUEAR JSON MALFORMADO

    malformed = FakeModel("resposta sem formato json")

    assert_rejected(current, malformed)

    print("[OK] Resposta fora do contrato rejeitada.")

    print("")
    print("========================================")
    print(" FASE 11.3 - TESTES OFFLINE APROVADOS")
    print("========================================")
    print("Testes: 6")
    print("Chamadas reais ao Ollama: 0")
    print("Alteracoes no PostgreSQL: 0")
    print("Acoes operacionais: 0")


if __name__ == "__main__":
    main()
