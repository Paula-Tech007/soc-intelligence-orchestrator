"""
FASE 13.8.4
Testes offline do adaptador persistente.
"""

import copy
import hashlib
import json
import unittest

from pathlib import Path
from unittest.mock import patch

import src.ai_engine.persistent_bridge as bridge

from src.ai_engine.integrity_persistence import (
    IntegrityConflictError,
)


ROOT = Path(__file__).resolve().parents[1]

FIXTURE = (
    ROOT / "tests/fixtures"
    / "wf04_wf05_integrity_mock.json"
)


def load_fixture():

    return json.loads(
        FIXTURE.read_text(encoding="utf-8-sig")
    )


def make_receipt(record, status="NEW_RESULT"):

    return {
        "status": status,
        "record_id": 1,
        "result_key": record["result_key"],
        "analysis_signature": record["analysis_signature"],
        "verified_against_database": True,
        "operational_dispatch_allowed": False,
    }


class PersistentBridgeTests(unittest.TestCase):

    def setUp(self):

        self.envelope = load_fixture()

        self.original = copy.deepcopy(
            self.envelope
        )

    def tearDown(self):

        self.assertEqual(
            self.envelope,
            self.original,
            "O contrato original foi modificado.",
        )

    # ------------------------------------------------------
    # TESTE 1 - PRIMEIRA PERSISTENCIA
    # ------------------------------------------------------

    def test_01_new_result(self):

        def fake_persistence(record):
            return make_receipt(record)

        with patch.object(
            bridge,
            "persist_integrity_record",
            side_effect=fake_persistence,
        ) as db:

            result = (
                bridge.prepare_persisted_integrity_contract(
                    self.envelope
                )
            )

        self.assertEqual(db.call_count, 1)

        self.assertEqual(
            result["integrity"]["status"],
            "PERSISTED_VALID",
        )

        self.assertEqual(
            result["integrity"]["persistence_status"],
            "NEW_RESULT",
        )

        self.assertTrue(
            result["integrity"]["verified_against_database"]
        )

        self.assertEqual(
            result["integrity"]["database_record_id"],
            1,
        )

        self.assertEqual(
            result["handoff"]["status"],
            "READY_FOR_PERSISTED_MOCK_REPORT",
        )

        self.assertTrue(
            result["handoff"]["human_review_required"]
        )

        self.assertFalse(
            result["ready_for_operational_dispatch"]
        )

        self.assertFalse(
            result["integrity"]["operational_dispatch_allowed"]
        )

        print("[OK] NEW_RESULT confirmado.")

    # ------------------------------------------------------
    # TESTE 2 - REPETICAO IDENTICA
    # ------------------------------------------------------

    def test_02_already_registered(self):

        def fake_persistence(record):

            return make_receipt(
                record,
                status="ALREADY_REGISTERED",
            )

        with patch.object(
            bridge,
            "persist_integrity_record",
            side_effect=fake_persistence,
        ):

            result = (
                bridge.prepare_persisted_integrity_contract(
                    self.envelope
                )
            )

        self.assertEqual(
            result["integrity"]["persistence_status"],
            "ALREADY_REGISTERED",
        )

        self.assertTrue(
            result["integrity"]["verified_against_database"]
        )

        self.assertFalse(
            result["handoff"]["operational_dispatch_allowed"]
        )

        print("[OK] ALREADY_REGISTERED confirmado.")

    # ------------------------------------------------------
    # TESTE 3 - BANCO INDISPONIVEL
    # ------------------------------------------------------

    def test_03_database_unavailable(self):

        with patch.object(
            bridge,
            "persist_integrity_record",
            side_effect=ConnectionError(
                "Banco MOCK indisponivel."
            ),
        ):

            with self.assertRaises(ConnectionError):

                bridge.prepare_persisted_integrity_contract(
                    self.envelope
                )

        print("[OK] Falha de conexao propagada.")

    # ------------------------------------------------------
    # TESTE 4 - CONFLITO DE INTEGRIDADE
    # ------------------------------------------------------

    def test_04_integrity_conflict(self):

        with patch.object(
            bridge,
            "persist_integrity_record",
            side_effect=IntegrityConflictError(
                "INTEGRITY_CONFLICT: MOCK."
            ),
        ):

            with self.assertRaises(
                IntegrityConflictError
            ):

                bridge.prepare_persisted_integrity_contract(
                    self.envelope
                )

        print("[OK] Conflito bloqueado.")

    # ------------------------------------------------------
    # TESTE 5 - ASSINATURA DIVERGENTE NO COMPROVANTE
    # ------------------------------------------------------

    def test_05_invalid_database_signature(self):

        def fake_persistence(record):

            receipt = make_receipt(record)

            receipt["analysis_signature"] = "0" * 64

            return receipt

        with patch.object(
            bridge,
            "persist_integrity_record",
            side_effect=fake_persistence,
        ):

            with self.assertRaises(
                bridge.PersistenceContractError
            ):

                bridge.prepare_persisted_integrity_contract(
                    self.envelope
                )

        print("[OK] Assinatura divergente rejeitada.")

    # ------------------------------------------------------
    # TESTE 6 - CONFIRMACAO DO BANCO AUSENTE
    # ------------------------------------------------------

    def test_06_database_not_verified(self):

        def fake_persistence(record):

            receipt = make_receipt(record)

            receipt["verified_against_database"] = False

            return receipt

        with patch.object(
            bridge,
            "persist_integrity_record",
            side_effect=fake_persistence,
        ):

            with self.assertRaises(
                bridge.PersistenceContractError
            ):

                bridge.prepare_persisted_integrity_contract(
                    self.envelope
                )

        print("[OK] Comprovante nao confirmado rejeitado.")

    # ------------------------------------------------------
    # TESTE 7 - IDENTIFICADOR INVALIDO
    # ------------------------------------------------------

    def test_07_invalid_record_id(self):

        def fake_persistence(record):

            receipt = make_receipt(record)

            # Booleano nao deve ser aceito como ID inteiro.
            receipt["record_id"] = True

            return receipt

        with patch.object(
            bridge,
            "persist_integrity_record",
            side_effect=fake_persistence,
        ):

            with self.assertRaises(
                bridge.PersistenceContractError
            ):

                bridge.prepare_persisted_integrity_contract(
                    self.envelope
                )

        print("[OK] Identificador invalido rejeitado.")

    # ------------------------------------------------------
    # TESTE 8 - ASSINATURA ALTERADA ANTES DA PERSISTENCIA
    # ------------------------------------------------------

    def test_08_upstream_integrity_tampering(self):

        original_function = (
            bridge.prepare_integrity_contract
        )

        def tampered_preparation(envelope):

            prepared = original_function(envelope)

            prepared["integrity"]["analysis_signature"] = (
                "0" * 64
            )

            return prepared

        with (
            patch.object(
                bridge,
                "prepare_integrity_contract",
                side_effect=tampered_preparation,
            ),
            patch.object(
                bridge,
                "persist_integrity_record",
            ) as db,
        ):

            with self.assertRaises(
                bridge.PersistenceContractError
            ):

                bridge.prepare_persisted_integrity_contract(
                    self.envelope
                )

            db.assert_not_called()

        print(
            "[OK] Adulteracao bloqueada antes do banco."
        )


def main():

    print()
    print("=" * 58)
    print(" FASE 13.8.4 - TESTES OFFLINE")
    print("=" * 58)

    # Preservar o fixture original.
    fixture_before = hashlib.sha256(
        FIXTURE.read_bytes()
    ).hexdigest()

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        PersistentBridgeTests
    )

    result = unittest.TextTestRunner(
        verbosity=2
    ).run(suite)

    fixture_after = hashlib.sha256(
        FIXTURE.read_bytes()
    ).hexdigest()

    if fixture_before != fixture_after:
        raise RuntimeError(
            "O fixture original foi modificado."
        )

    if (
        not result.wasSuccessful()
        or result.testsRun != 8
    ):
        raise RuntimeError(
            "FASE 13.8.4 nao aprovada."
        )

    print()
    print("=" * 58)
    print(" FASE 13.8.4 - VALIDACAO CONCLUIDA")
    print("=" * 58)

    print("Testes aprovados: 8/8")
    print("Persistencia: SIMULADA")
    print("Chamadas reais ao PostgreSQL: 0")
    print("Chamadas reais ao Ollama: 0")
    print("Fixture original: PRESERVADO")
    print("Despacho operacional: BLOQUEADO")

    print()
    print("[OK] ADAPTADOR PERSISTENTE VALIDADO OFFLINE")


if __name__ == "__main__":
    main()
