"""
FASE 13.5.3 - Testes offline do adaptador.
"""

import copy
import json
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ai_engine.integrity import IntegrityRegistry
from src.ai_engine.integrity_bridge import (
    prepare_integrity_contract,
)

from src.reports.report_builder import build_report


def main():

    fixture = (
        ROOT / "tests/fixtures/wf04_output_mock.json"
    )

    original = json.loads(
        fixture.read_text(encoding="utf-8")
    )

    registry = IntegrityRegistry()

    print()
    print("=== FASE 13.5.3 - TESTES DO ADAPTADOR ===")

    # TESTE 1 - PRIMEIRO REGISTRO

    first = prepare_integrity_contract(
        original,
        registry,
    )

    assert first["integrity"]["status"] == "VALID"

    assert (
        first["integrity"]["registry_status"]
        == "NEW_RESULT"
    )

    print("[OK] Primeiro resultado registrado.")

    # TESTE 2 - ASSINATURAS PRESENTES

    integrity = first["integrity"]

    assert len(integrity["content_signature"]) == 64
    assert len(integrity["analysis_signature"]) == 64
    assert len(integrity["result_key"]) == 64

    assert (
        integrity["content_signature"]
        != integrity["analysis_signature"]
    )

    print("[OK] Assinaturas independentes presentes.")

    # TESTE 3 - REPETICAO IDENTICA

    repeated = prepare_integrity_contract(
        original,
        registry,
    )

    assert (
        repeated["integrity"]["registry_status"]
        == "ALREADY_REGISTERED"
    )

    print("[OK] Reprocessamento identico reconhecido.")

    # TESTE 4 - CONFLITO DE ANALISE

    changed = copy.deepcopy(original)

    changed["results"][1]["analysis"]["summary"] = (
        "TESTE-INTEGRIDADE-1353"
    )

    try:
        prepare_integrity_contract(changed, registry)

    except ValueError as exc:

        assert "INTEGRITY_CONFLICT" in str(exc)

        print("[OK] Analise divergente bloqueada.")

    else:

        raise AssertionError(
            "Reprocessamento conflitante foi aceito."
        )

    # TESTE 5 - CONTRATO SEGUE COMPATIVEL COM O WF-05

    html = build_report(first)

    assert "LAB-EV-001" in html
    assert "LAB-EV-002" in html

    assert (
        first["handoff"]["status"]
        == "READY_FOR_MOCK_REPORT"
    )

    assert first["handoff"]["selected_queue_id"] == 13

    assert (
        first["handoff"]["operational_dispatch_allowed"]
        is False
    )

    print("[OK] Contrato compativel com o WF-05.")

    # TESTE 6 - FONTE ORIGINAL NAO MODIFICADA

    saved = json.loads(
        fixture.read_text(encoding="utf-8")
    )

    assert saved == original

    assert "integrity" not in original
    assert "handoff" not in original

    print("[OK] Fixture original preservado.")

    print()
    print("========================================")
    print(" FASE 13.5.3 - TESTES APROVADOS")
    print("========================================")
    print("Testes: 6")
    print("Ollama: 0 chamadas")
    print("PostgreSQL: sem acesso")
    print("Notificacoes: nenhuma")
    print("Registro: somente memoria")
    print()
    print("[OK] ADAPTADOR DE INTEGRIDADE VALIDADO")


if __name__ == "__main__":
    main()
