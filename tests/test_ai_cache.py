"""
FASE 11.5.2 - Testes offline do cache WF-04.
"""

import copy
import json
import sys

from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ai_engine.cache import AnalysisCache
from test_ai_engine_live import prepare_context


class FakeModel:

    def __init__(self):
        self.calls = 0

    def invoke(self, messages):

        self.calls += 1

        return SimpleNamespace(
            content=json.dumps({
                "summary": "Evento sintetico para revisao.",
                "assessment": "Duas evidencias em LAB.",
                "evidence_ids": [
                    "LAB-EV-001",
                    "LAB-EV-002",
                ],
                "limitations": [
                    "Correlacoes sao informativas."
                ],
                "review_actions": [
                    "Revisar as evidencias."
                ],
            })
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

    historical = prepare_context(versions[1])
    current = prepare_context(versions[2])

    cache = AnalysisCache()
    model = FakeModel()

    print("")
    print("=== FASE 11.5.2 - CACHE WF-04 ===")

    # TESTE 1 - HISTORICO NAO ACIONA MODELO

    a = cache.run_mock(historical, model)

    assert a["status"] == "SKIPPED"
    assert model.calls == 0

    print("[OK] Versao historica bloqueada.")

    # TESTE 2 - PRIMEIRA ANALISE DA VERSAO ATUAL

    b = cache.run_mock(current, model)

    assert b["status"] == "ANALYSIS_COMPLETED"
    assert b["cache_hit"] is False
    assert b["model_invoked_this_call"] is True
    assert model.calls == 1

    print("[OK] Primeira analise executada.")

    # TESTE 3 - REPETICAO REUTILIZA RESULTADO

    c = cache.run_mock(current, model)

    assert c["cache_hit"] is True
    assert c["model_invoked_this_call"] is False
    assert model.calls == 1

    assert c["analysis"] == b["analysis"]

    print("[OK] Repeticao reutilizou o cache.")

    # TESTE 4 - MUTACAO NO MESMO CONTEXTO E BLOQUEADA

    altered = copy.deepcopy(current)
    altered["event"]["severity"] = "critical"

    try:
        cache.run_mock(altered, model)

    except ValueError:
        pass

    else:
        raise AssertionError(
            "Mutacao silenciosa nao foi bloqueada."
        )

    assert model.calls == 1

    print("[OK] Conteudo alterado na mesma versao bloqueado.")

    # TESTE 5 - NOVA VERSAO EXIGE NOVA ANALISE

    new_version = copy.deepcopy(current)

    new_version["requested_version"] = 3
    new_version["current_version"] = 3
    new_version["provenance"]["version"] = 3

    new_version["provenance"]["content_signature"] = (
        "LAB-SYNTHETIC-CACHE-TEST-V3"
    )

    d = cache.run_mock(new_version, model)

    assert d["cache_hit"] is False
    assert model.calls == 2

    print("[OK] Nova versao exigiu nova analise.")

    print("")
    print("========================================")
    print(" CACHE WF-04 VALIDADO")
    print("========================================")
    print("Testes: 5")
    print("Chamadas simuladas: 2")
    print("Chamadas reais ao Ollama: 0")
    print("Gravacoes no PostgreSQL: 0")
    print("Persistencia do cache: somente memoria")
    print("")
    print("[OK] FASE 11.5.2 APROVADA")


if __name__ == "__main__":
    main()
