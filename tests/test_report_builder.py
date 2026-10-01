"""
FASE 12.2 - Testes do gerador de relatorios WF-05.
"""

import copy
import json
import sys
import tempfile

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT))

from src.reports.report_builder import (
    build_report,
    validate_contract,
)


def assert_rejected(data):

    try:
        build_report(data)
    except ValueError:
        return

    raise AssertionError(
        "O contrato invalido nao foi bloqueado."
    )


def main():

    fixture = (
        ROOT / "tests" / "fixtures"
        / "wf04_output_mock.json"
    )

    contract = json.loads(
        fixture.read_text(encoding="utf-8")
    )

    print("")
    print("=== FASE 12.2 - TESTES DO WF-05 ===")

    # TESTE 1 - VALIDAR CONTRATO ORIGINAL

    historical, current = validate_contract(contract)

    assert historical["status"] == "SKIPPED"
    assert current["status"] == "ANALYSIS_COMPLETED"

    print("[OK] Contrato WF-04 validado.")

    # TESTE 2 - GERAR HTML

    result = build_report(contract)

    assert "<!DOCTYPE html>" in result
    assert "LABORATORIO - ANALISE SIMULADA" in result
    assert "LAB-EV-001" in result
    assert "LAB-EV-002" in result
    assert current["provenance"]["content_signature"] in result

    print("[OK] HTML gerado com rastreabilidade.")

    # TESTE 3 - BLOQUEAR HISTORICO INDEVIDO

    invalid = copy.deepcopy(contract)

    invalid["results"][0]["status"] = "ANALYSIS_COMPLETED"

    assert_rejected(invalid)

    print("[OK] Versao historica indevida bloqueada.")

    # TESTE 4 - BLOQUEAR DESPACHO OPERACIONAL

    invalid = copy.deepcopy(contract)

    invalid["ready_for_operational_dispatch"] = True

    assert_rejected(invalid)

    print("[OK] Despacho operacional bloqueado.")

    # TESTE 5 - EVITAR INJECAO DE HTML

    injected = copy.deepcopy(contract)

    injected["results"][1]["analysis"]["summary"] = (
        "<script>alert('lab')</script>"
    )

    escaped = build_report(injected)

    assert "<script>" not in escaped
    assert "&lt;script&gt;" in escaped

    print("[OK] Conteudo HTML potencialmente inseguro escapado.")

    # TESTE 6 - REFERENCIA DE EVIDENCIA INVALIDA

    invalid = copy.deepcopy(contract)

    invalid["results"][1]["analysis"]["evidence_ids"] = [
        "LAB-EV-999"
    ]

    assert_rejected(invalid)

    print("[OK] Evidencia desconhecida bloqueada.")

    # TESTE 7 - GRAVAR E RELER EM DIRETORIO TEMPORARIO

    with tempfile.TemporaryDirectory() as temporary:

        file = Path(temporary) / "soc_lab_report.html"

        file.write_text(
            result,
            encoding="utf-8"
        )

        saved = file.read_text(encoding="utf-8")

        assert saved == result

    print("[OK] Gravacao e leitura HTML validadas.")

    print("")
    print("========================================")
    print(" FASE 12.2 - TESTES APROVADOS")
    print("========================================")
    print("Testes: 7")
    print("Chamadas ao Ollama: 0")
    print("Gravacoes no PostgreSQL: 0")
    print("Notificacoes enviadas: 0")
    print("Relatorio: HTML em modo LAB/MOCK")


if __name__ == "__main__":
    main()
