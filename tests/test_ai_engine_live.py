"""
SOC Intelligence Orchestrator
FASE 11.4 - Teste real WF-04.

Modelo: qwen3:4b-instruct
Integracao: LangChain + Ollama local.

Nao altera PostgreSQL.
Nao executa acoes operacionais.
"""

import json
import os
import sys

from pathlib import Path


# Desabilitar tracing externo para este teste.
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT))

from src.ai_engine.engine import analyze


class ForbiddenModel:
    """Falha imediatamente caso receba uma chamada."""

    def invoke(self, messages):

        raise AssertionError(
            "ERRO: versao historica tentou chamar a IA."
        )


def prepare_context(snapshot):

    eligible = snapshot["eligible_for_context_review"]

    return {
        "schema_version": "1.0",
        "environment": "LAB",
        "processor": "WF-03",

        "queue_id": snapshot["queue_id"],

        "investigation_id": snapshot[
            "investigation_id"
        ],

        "source_event_id": snapshot[
            "source_event_id"
        ],

        "requested_version": snapshot[
            "requested_version"
        ],

        "current_version": snapshot[
            "current_version"
        ],

        "context_status": snapshot[
            "context_status"
        ],

        "is_historical_version": snapshot[
            "is_historical_version"
        ],

        "event": snapshot["event"],

        "changed_fields": snapshot[
            "changed_fields"
        ],

        "evidence_count": snapshot[
            "evidence_count"
        ],

        "indicators": snapshot["indicators"],

        "correlations": snapshot[
            "correlations"
        ],

        "provenance": snapshot["provenance"],

        "decision": {
            "eligible_for_ai": eligible,
            "target_workflow": (
                "WF-04" if eligible else None
            ),
        },

        "validation_status": "VALID",

        "dispatch_status": "MOCK_ONLY",

        "real_execution_started": False,

        "ai_executed": False,

        "notification_sent": False,
    }


def main():

    snapshot_path = (
        ROOT
        / "tests"
        / "fixtures"
        / "wf03_context_snapshot.json"
    )

    if not snapshot_path.is_file():
        raise FileNotFoundError(
            "Snapshot do WF-03 nao encontrado."
        )

    snapshots = json.loads(
        snapshot_path.read_text(
            encoding="utf-8"
        )
    )

    by_version = {
        item["requested_version"]: item
        for item in snapshots
    }

    if set(by_version) != {1, 2}:
        raise RuntimeError(
            "Esperadas as versoes 1 e 2."
        )

    historical = prepare_context(
        by_version[1]
    )

    current = prepare_context(
        by_version[2]
    )

    print("")
    print("========================================")
    print(" SOC LAB - TESTE REAL DO MOTOR DE IA")
    print("========================================")

    # ======================================================
    # TESTE 1 - BLOQUEIO DA VERSAO HISTORICA
    # ======================================================

    print("")
    print("=== 1. TESTANDO VERSAO HISTORICA ===")

    result_historical = analyze(
        historical,
        model=ForbiddenModel()
    )

    assert result_historical["status"] == "SKIPPED"

    assert result_historical["ai_executed"] is False

    print("[OK] Versao 1 ignorada.")
    print("[OK] Nenhuma chamada ao modelo.")

    # ======================================================
    # TESTE 2 - CHAMADA REAL AO QWEN
    # ======================================================

    print("")
    print("=== 2. ANALISANDO VERSAO ATUAL ===")

    print("Evento: LAB-0001")
    print("Versao: 2")
    print("Modelo: qwen3:4b-instruct")
    print("Destino: Ollama local")

    print("")
    print("Aguardando resposta do modelo...")

    # model=None faz o engine.py utilizar ChatOllama real.

    result_current = analyze(
        current,
        model=None
    )

    # ======================================================
    # VALIDAR A RESPOSTA
    # ======================================================

    assert (
        result_current["status"]
        == "ANALYSIS_COMPLETED"
    )

    assert result_current["ai_executed"] is True

    assert (
        result_current["requires_human_review"]
        is True
    )

    assert (
        result_current["notification_sent"]
        is False
    )

    assert (
        result_current["real_execution_started"]
        is False
    )

    analysis = result_current["analysis"]

    allowed = {
        "LAB-EV-001",
        "LAB-EV-002",
    }

    assert set(
        analysis["evidence_ids"]
    ).issubset(allowed)

    # ======================================================
    # EXIBIR RESULTADO ESTRUTURADO
    # ======================================================

    print("")
    print("========================================")
    print(" RESULTADO REAL DA IA")
    print("========================================")

    print(
        json.dumps(
            result_current,
            indent=2,
            ensure_ascii=False
        )
    )

    print("")
    print("========================================")
    print(" VALIDACAO FINAL")
    print("========================================")

    print("[OK] Versao historica bloqueada.")

    print("[OK] Versao atual analisada pelo Qwen.")

    print("[OK] JSON validado.")

    print("[OK] Evidencias verificadas.")

    print("[OK] Revisao humana obrigatoria.")

    print("[OK] Nenhuma notificacao enviada.")

    print("[OK] Nenhuma gravacao no PostgreSQL.")

    print("")
    print("FASE 11.4 - TESTE REAL APROVADO.")


if __name__ == "__main__":
    main()