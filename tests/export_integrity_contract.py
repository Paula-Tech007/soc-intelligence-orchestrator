"""
FASE 13.6.1 - Exportador de contrato com integridade.

Utiliza exclusivamente o fixture LAB do WF-04.
Nao executa IA, banco de dados ou notificacoes.
"""

import json
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT))

from src.ai_engine.integrity_bridge import (
    prepare_integrity_contract,
)

from src.ai_engine.integrity import (
    build_integrity_record,
    verify_integrity_record,
    sha256_json,
)

from src.reports.report_builder import validate_contract


def main():

    source = (
        ROOT / "tests/fixtures/wf04_output_mock.json"
    )

    destination = (
        ROOT / "tests/fixtures/"
        "wf04_wf05_integrity_mock.json"
    )

    if not source.is_file():
        raise FileNotFoundError(
            "Contrato WF-04 nao encontrado."
        )

    if destination.exists():
        raise FileExistsError(
            "Contrato de integridade ja existe. "
            "Nenhum arquivo sera sobrescrito."
        )

    original = json.loads(
        source.read_text(encoding="utf-8")
    )

    # Validar contrato original e obter versao elegivel.

    historical, current = validate_contract(original)

    if historical["status"] != "SKIPPED":
        raise RuntimeError(
            "Versao historica inesperada."
        )

    if current["status"] != "ANALYSIS_COMPLETED":
        raise RuntimeError(
            "Analise atual inesperada."
        )

    # Preparar envelope com assinaturas independentes.

    envelope = prepare_integrity_contract(original)

    integrity = envelope["integrity"]

    # Reconstruir o registro para verificar os hashes.
    # Os campos de transporte sao MOCK e nao representam
    # uma execucao real do modelo neste procedimento.

    current_result = dict(current)

    current_result.update({
        "fixture_type": "MOCK_AI_RESPONSE",
        "real_ollama_call": False,
        "ready_for_operational_dispatch": False,
    })

    record = build_integrity_record(current_result)

    verify_integrity_record(record)

    assert integrity["status"] == "VALID"

    assert (
        integrity["content_signature"]
        == record["content_signature"]
    )

    assert (
        integrity["analysis_signature"]
        == record["analysis_signature"]
    )

    assert (
        integrity["result_key"]
        == record["result_key"]
    )

    assert envelope["handoff"][
        "selected_queue_id"
    ] == 13

    assert envelope["handoff"][
        "selected_version"
    ] == 2

    assert envelope["handoff"][
        "operational_dispatch_allowed"
    ] is False

    # Identificador adicional do envelope exportado.
    # Nao representa assinatura de autenticidade.

    envelope["export_metadata"] = {
        "schema_version": "1.0",
        "export_mode": "LAB_MOCK",
        "origin": "PYTHON_INTEGRITY_BRIDGE",
        "envelope_digest": sha256_json(envelope),
        "database_verified": False,
        "real_ollama_call": False,
        "notification_sent": False,
    }

    destination.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    destination.write_text(
        json.dumps(
            envelope,
            ensure_ascii=False,
            indent=2
        ) + "\n",
        encoding="utf-8"
    )

    # Validar o arquivo gravado.

    saved = json.loads(
        destination.read_text(encoding="utf-8")
    )

    assert saved == envelope

    validate_contract(saved)

    print()
    print("=" * 55)
    print(" FASE 13.6.1 - CONTRATO DE INTEGRIDADE")
    print("=" * 55)

    print("Arquivo:", destination.resolve())

    print()
    print("CONTROLE DE VERSOES:")
    print("Historica: 1 / SKIPPED")
    print("Atual: 2 / ANALYSIS_COMPLETED")

    print()
    print("ASSINATURAS:")

    for field in (
        "content_signature",
        "analysis_signature",
        "result_key",
    ):
        value = saved["integrity"][field]

        assert len(value) == 64

        print(f"{field}: {value}")

    print()
    print("Registro:", integrity["registry_status"])
    print("Integridade: VALID")
    print("Destino: WF-05")
    print("Verificacao no banco: NAO")
    print("Ollama acionado: NAO")
    print("Notificacoes: NENHUMA")

    print()
    print("[OK] CONTRATO DE INTEGRIDADE EXPORTADO")


if __name__ == "__main__":
    main()
