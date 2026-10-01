
import copy
import json
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.reports.report_builder import (
    build_report,
    validate_contract,
)


def pack_wf04_results(items):
    """
    Adapta dois resultados individuais do WF-04
    para o contrato recebido pelo WF-05.
    """

    if not isinstance(items, list) or len(items) != 2:
        raise ValueError("Esperados dois resultados WF-04.")

    if any(
        not isinstance(item, dict)
        or item.get("environment") != "LAB"
        or item.get("processor") != "WF-04"
        or item.get("dispatch_status") != "MOCK_ONLY"
        or item.get("fixture_type") != "MOCK_AI_RESPONSE"
        or item.get("real_ollama_call") is not False
        or item.get("ready_for_operational_dispatch") is not False
        for item in items
    ):
        raise ValueError("Resultado fora do contrato LAB/MOCK.")

    if {x.get("investigation_version") for x in items} != {1, 2}:
        raise ValueError("Versoes recebidas inconsistentes.")

    envelope = {
        "schema_version": "1.0",
        "environment": "LAB",
        "origin": "WF-04",
        "fixture_type": "MOCK_AI_RESPONSE",
        "real_ollama_call": False,
        "ready_for_operational_dispatch": False,
        "results": copy.deepcopy(items),
    }

    validate_contract(envelope)

    return envelope


def main():

    source = (
        ROOT / "tests" / "fixtures"
        / "wf04_output_mock.json"
    )

    fixture = json.loads(
        source.read_text(encoding="utf-8")
    )

    # Reproduzir a estrutura dos dois itens individuais
    # entregues pelo ultimo node do WF-04.

    incoming_items = []

    for result in fixture["results"]:

        item = copy.deepcopy(result)

        item["fixture_type"] = "MOCK_AI_RESPONSE"
        item["real_ollama_call"] = False
        item["ready_for_operational_dispatch"] = False

        incoming_items.append(item)

    print()
    print("=== FASE 13.2 - HANDOFF WF-04 / WF-05 ===")

    # TESTE 1 - AGRUPAR OS DOIS RESULTADOS

    envelope = pack_wf04_results(incoming_items)

    assert len(envelope["results"]) == 2

    print("[OK] Dois itens agrupados em um contrato.")

    # TESTE 2 - VALIDAR BLOQUEIO HISTORICO

    historical, current = validate_contract(envelope)

    assert historical["status"] == "SKIPPED"
    assert current["status"] == "ANALYSIS_COMPLETED"

    print("[OK] Versao historica preservada como SKIPPED.")

    # TESTE 3 - GERAR HTML A PARTIR DO NOVO CONTRATO

    html = build_report(envelope)

    assert "LAB-EV-001" in html
    assert "LAB-EV-002" in html
    assert current["provenance"]["content_signature"] in html

    print("[OK] WF-05 recebeu o contrato agrupado.")

    # TESTE 4 - CONFIRMAR QUE O RELATORIO NAO
    # DEPENDE DE TEXTO ESTATICO INCORPORADO.

    changed = copy.deepcopy(incoming_items)

    marker = "MARCADOR-DINAMICO-LAB-132"

    for item in changed:

        if item["investigation_version"] == 2:

            item["analysis"]["summary"] = marker

    dynamic = pack_wf04_results(changed)

    dynamic_html = build_report(dynamic)

    assert marker in dynamic_html
    assert marker not in html

    print("[OK] Alteracao de entrada refletida no HTML.")

    # TESTE 5 - BLOQUEAR PROMOCAO DA VERSAO HISTORICA

    invalid = copy.deepcopy(incoming_items)

    for item in invalid:

        if item["investigation_version"] == 1:
            item["status"] = "ANALYSIS_COMPLETED"

    try:
        pack_wf04_results(invalid)

    except ValueError:
        print("[OK] Historico indevido bloqueado.")

    else:
        raise AssertionError(
            "Versao historica alterada foi aceita."
        )

    print()
    print("========================================")
    print(" FASE 13.2 - TESTES OFFLINE APROVADOS")
    print("========================================")
    print("Testes: 5")
    print("Entrada: 2 itens WF-04")
    print("Saida: 1 contrato WF-05")
    print("Ollama: 0 chamadas")
    print("PostgreSQL: sem acesso")
    print("n8n remoto: sem alteracoes")


if __name__ == "__main__":
    main()
