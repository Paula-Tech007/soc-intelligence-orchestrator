"""
FASE 13.5.2 - Testes offline de integridade.
"""

import copy
import json
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT))

from src.ai_engine.integrity import (
    IntegrityRegistry,
    build_integrity_record,
    sha256_json,
    verify_integrity_record,
)


def reject(callback):

    try:
        callback()

    except ValueError:
        return

    raise AssertionError(
        "Operacao inconsistente foi aceita."
    )


def main():

    fixture_path = (
        ROOT / "tests/fixtures/wf04_output_mock.json"
    )

    fixture = json.loads(
        fixture_path.read_text(encoding="utf-8")
    )

    historical, current = fixture["results"]

    # Reproduzir os campos adicionados pelo n8n WF-04.

    current = copy.deepcopy(current)

    current["fixture_type"] = "MOCK_AI_RESPONSE"
    current["real_ollama_call"] = False
    current["ready_for_operational_dispatch"] = False

    print()
    print("=== FASE 13.5.2 - TESTES DE INTEGRIDADE ===")

    # TESTE 1 - CRIAR DUAS ASSINATURAS INDEPENDENTES

    record = build_integrity_record(current)

    assert len(record["analysis_signature"]) == 64
    assert len(record["content_signature"]) == 64

    assert (
        record["content_signature"]
        == current["provenance"]["content_signature"]
    )

    assert record["analysis_signature"] != (
        record["content_signature"]
    )

    print("[OK] Contexto e analise possuem assinaturas distintas.")

    # TESTE 2 - VALIDAR DETERMINISMO DO HASH JSON

    a = {"a": 1, "b": 2}
    b = {"b": 2, "a": 1}

    assert sha256_json(a) == sha256_json(b)

    print("[OK] Hash JSON independente da ordem das chaves.")

    # TESTE 3 - REPETICAO IDENTICA

    registry = IntegrityRegistry()

    assert registry.register(record) == "NEW_RESULT"

    assert (
        registry.register(copy.deepcopy(record))
        == "ALREADY_REGISTERED"
    )

    print("[OK] Repeticao identica identificada.")

    # TESTE 4 - MESMO CONTEXTO COM ANALISE DIFERENTE

    changed = copy.deepcopy(current)

    changed["analysis"]["summary"] = (
        "ANALISE-DIFERENTE-FASE-135"
    )

    changed_record = build_integrity_record(changed)

    assert (
        changed_record["content_signature"]
        == record["content_signature"]
    )

    assert (
        changed_record["analysis_signature"]
        != record["analysis_signature"]
    )

    assert (
        changed_record["result_key"]
        == record["result_key"]
    )

    reject(
        lambda: registry.register(changed_record)
    )

    print("[OK] Conflito de reprocessamento detectado.")

    # TESTE 5 - ALTERACAO DEPOIS DA ASSINATURA

    tampered = copy.deepcopy(record)

    tampered["analysis"]["assessment"] = (
        "Conteudo alterado apos assinatura."
    )

    reject(
        lambda: verify_integrity_record(tampered)
    )

    print("[OK] Analise modificada apos assinatura bloqueada.")

    # TESTE 6 - MODELO DIFERENTE

    other_model = copy.deepcopy(current)

    other_model["model"] = "MODELO-ALTERNATIVO-MOCK"

    other_record = build_integrity_record(other_model)

    assert (
        other_record["result_key"]
        != record["result_key"]
    )

    print("[OK] Modelo diferente gera outra chave.")

    # TESTE 7 - VERSAO HISTORICA

    reject(
        lambda: build_integrity_record(historical)
    )

    print("[OK] Versao historica nao pode ser assinada como analise.")

    # TESTE 8 - ASSINATURA DE CONTEXTO INVALIDA

    invalid = copy.deepcopy(current)

    invalid["provenance"]["content_signature"] = "INVALIDA"

    reject(
        lambda: build_integrity_record(invalid)
    )

    print("[OK] Assinatura de contexto invalida rejeitada.")

    print()
    print("=" * 50)
    print(" FASE 13.5.2 - TESTES APROVADOS")
    print("=" * 50)
    print("Testes: 8")
    print("Ollama: nenhuma chamada")
    print("PostgreSQL: sem acesso")
    print("Registro: somente memoria")
    print("Workflows originais: preservados")
    print()
    print("[OK] MODULO DE INTEGRIDADE VALIDADO")


if __name__ == "__main__":
    main()
