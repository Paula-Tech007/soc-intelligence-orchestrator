"""
FASE 13.9.3 - Testes do gate persistente WF-05.

Usa os dois registros LAB ja existentes.
Nao cria novas investigacoes.
Nao modifica os workflows.
"""

import copy
import hashlib
import json
import unittest

from pathlib import Path
from unittest.mock import patch

from psycopg.rows import tuple_row

from src.ai_engine.persistent_bridge import (
    prepare_persisted_integrity_contract,
)

import src.reports.persistent_handoff as gate

from src.dedup.persistence import connect_db


ROOT = Path(__file__).resolve().parents[1]

FIXTURE = (
    ROOT / "tests/fixtures"
    / "wf04_wf05_integrity_mock.json"
)


def snapshot():

    with connect_db() as conn:

        with conn.cursor(row_factory=tuple_row) as cur:

            cur.execute("""
                SELECT
                    id,
                    investigation_id::text,
                    investigation_version,
                    queue_id,
                    source_event_id,
                    model_id,
                    execution_mode,
                    content_signature::text,
                    analysis_signature::text,
                    result_key::text,
                    analysis_data,
                    status,
                    operational_dispatch_allowed
                FROM public.ai_analysis_integrity
                ORDER BY id;
            """)

            return cur.fetchall()


class GateTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cls.before = snapshot()

        assert len(cls.before) == 2
        assert [row[0] for row in cls.before] == [1, 9]
        assert all(row[12] is False for row in cls.before)

        source = json.loads(
            FIXTURE.read_text(encoding="utf-8-sig")
        )

        source_original = copy.deepcopy(source)

        # A identidade ja esta registrada (ID 1).
        # Resultado esperado: ALREADY_REGISTERED.

        cls.contract = prepare_persisted_integrity_contract(
            source
        )

        assert source == source_original

        assert (
            cls.contract["integrity"]["persistence_status"]
            == "ALREADY_REGISTERED"
        )

        assert (
            cls.contract["integrity"]["database_record_id"]
            == 1
        )

        assert snapshot() == cls.before

        print()
        print("[OK] Contrato persistente obtido: ID 1.")
        print("[OK] PostgreSQL preservado apos o preflight.")

    def test_01_valid_contract(self):

        result = gate.validate_persisted_handoff(
            copy.deepcopy(self.contract)
        )

        validation = result[
            "persistent_handoff_validation"
        ]

        self.assertEqual(
            validation["status"],
            "VALIDATED",
        )

        self.assertEqual(
            validation["verification_method"],
            "POSTGRESQL_ROW_RECHECK",
        )

        self.assertEqual(
            validation["database_record_id"],
            1,
        )

        self.assertTrue(
            validation["human_review_required"]
        )

        self.assertFalse(
            validation["operational_dispatch_allowed"]
        )

        self.assertFalse(
            result["ready_for_operational_dispatch"]
        )

        self.assertNotIn(
            "persistent_handoff_validation",
            self.contract,
        )

        print("[OK] Gate liberou o contrato valido.")

    def test_02_nonexistent_database_record(self):

        changed = copy.deepcopy(self.contract)

        changed["integrity"][
            "database_record_id"
        ] = 999999999

        with self.assertRaises(
            gate.PersistentHandoffError
        ):
            gate.validate_persisted_handoff(changed)

        print("[OK] Registro inexistente rejeitado.")

    def test_03_wrong_existing_record(self):

        changed = copy.deepcopy(self.contract)

        # ID 9 existe, mas possui outro model_id
        # e outra identidade logica.

        changed["integrity"][
            "database_record_id"
        ] = 9

        with self.assertRaises(
            gate.PersistentHandoffError
        ):
            gate.validate_persisted_handoff(changed)

        print("[OK] Registro de outra identidade rejeitado.")

    def test_04_forged_signature(self):

        changed = copy.deepcopy(self.contract)

        changed["integrity"][
            "analysis_signature"
        ] = "0" * 64

        with self.assertRaises(
            gate.PersistentHandoffError
        ):
            gate.validate_persisted_handoff(changed)

        print("[OK] Assinatura adulterada bloqueada.")

    def test_05_modified_analysis(self):

        changed = copy.deepcopy(self.contract)

        for result in changed["results"]:

            if result["investigation_version"] == 2:

                result["analysis"]["summary"] = (
                    "Resumo adulterado no transporte LAB."
                )

        with self.assertRaises(
            gate.PersistentHandoffError
        ):
            gate.validate_persisted_handoff(changed)

        print("[OK] Analise modificada bloqueada.")

    def test_06_unverified_receipt(self):

        changed = copy.deepcopy(self.contract)

        changed["integrity"][
            "verified_against_database"
        ] = False

        with self.assertRaises(
            gate.PersistentHandoffError
        ):
            gate.validate_persisted_handoff(changed)

        print("[OK] Comprovante nao verificado rejeitado.")

    def test_07_invalid_handoff(self):

        changed = copy.deepcopy(self.contract)

        changed["handoff"][
            "selected_queue_id"
        ] = 12

        with self.assertRaises(
            gate.PersistentHandoffError
        ):
            gate.validate_persisted_handoff(changed)

        print("[OK] Fila divergente rejeitada.")

    def test_08_operational_dispatch(self):

        changed = copy.deepcopy(self.contract)

        changed[
            "ready_for_operational_dispatch"
        ] = True

        # A rejeicao deve ocorrer antes de
        # solicitar uma conexao PostgreSQL.

        with patch.object(
            gate,
            "connect_db",
        ) as database:

            with self.assertRaises(
                gate.PersistentHandoffError
            ):
                gate.validate_persisted_handoff(changed)

            database.assert_not_called()

        print("[OK] Despacho operacional bloqueado.")


def main():

    print()
    print("=" * 60)
    print(" FASE 13.9.3 - TESTES DO GATE PERSISTENTE")
    print("=" * 60)

    fixture_hash = hashlib.sha256(
        FIXTURE.read_bytes()
    ).hexdigest()

    before = snapshot()

    assert len(before) == 2
    assert [row[0] for row in before] == [1, 9]
    assert all(row[12] is False for row in before)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        GateTests
    )

    result = unittest.TextTestRunner(
        verbosity=2
    ).run(suite)

    after = snapshot()

    assert before == after, (
        "FALHA: estado PostgreSQL modificado."
    )

    assert fixture_hash == hashlib.sha256(
        FIXTURE.read_bytes()
    ).hexdigest(), (
        "FALHA: fixture original modificado."
    )

    if (
        not result.wasSuccessful()
        or result.testsRun != 8
    ):
        raise RuntimeError(
            "FASE 13.9.3 NAO APROVADA."
        )

    print()
    print("=" * 60)
    print(" FASE 13.9.3 - VALIDACAO CONCLUIDA")
    print("=" * 60)

    print("Testes aprovados: 8/8")
    print("Registros antes:", len(before))
    print("Registros depois:", len(after))
    print("Assinaturas: PRESERVADAS")
    print("Fixture original: PRESERVADO")
    print("Ollama: NAO ACIONADO")
    print("Notificacoes: NENHUMA")
    print("Despacho operacional: BLOQUEADO")

    print()
    print("[OK] GATE PERSISTENTE WF-05 VALIDADO")


if __name__ == "__main__":
    main()
