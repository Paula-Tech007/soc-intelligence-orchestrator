"""
FASE 13.9.4.3
Testes offline da integracao gate + gerador HTML.
"""

import copy
import unittest

from unittest.mock import patch

import src.reports.persistent_report as report

from src.reports.persistent_handoff import (
    PersistentHandoffError,
)


def valid_contract():

    return {
        "persistent_handoff_validation": {
            "status": "VALIDATED",
            "verification_method": "POSTGRESQL_ROW_RECHECK",
            "database_record_id": 1,
            "result_key": "a" * 64,
            "analysis_signature": "b" * 64,
            "human_review_required": True,
            "operational_dispatch_allowed": False,
        },
        "ready_for_operational_dispatch": False,
    }


class PersistentReportTests(unittest.TestCase):

    def setUp(self):

        self.source = {
            "scenario": "LAB-MOCK-REPORT"
        }

        self.original = copy.deepcopy(self.source)

    def tearDown(self):

        self.assertEqual(
            self.source,
            self.original,
            "Contrato de entrada modificado.",
        )

    # --------------------------------------------------
    # 01 - ORDEM OBRIGATORIA
    # --------------------------------------------------

    def test_01_gate_before_html(self):

        execution_order = []

        def fake_gate(contract):

            execution_order.append("GATE")

            return valid_contract()

        def fake_html(contract):

            execution_order.append("HTML")

            return "<!DOCTYPE html><html>LAB</html>"

        with (
            patch.object(
                report,
                "validate_persisted_handoff",
                side_effect=fake_gate,
            ) as gate,
            patch.object(
                report,
                "build_report",
                side_effect=fake_html,
            ) as builder,
        ):

            output = report.build_persisted_report(
                self.source
            )

        self.assertEqual(
            execution_order,
            ["GATE", "HTML"],
        )

        gate.assert_called_once()
        builder.assert_called_once()

        self.assertEqual(
            output["database_record_id"],
            1,
        )

        self.assertEqual(
            output["report_status"],
            "AWAITING_HUMAN_REVIEW",
        )

        self.assertTrue(
            output["persistent_handoff_validated"]
        )

        self.assertTrue(
            output["human_review_required"]
        )

        self.assertFalse(
            output["operational_dispatch_allowed"]
        )

        self.assertFalse(
            output["notification_sent"]
        )

        print("[OK] Gate executado antes do HTML.")

    # --------------------------------------------------
    # 02 - FALHA NO GATE BLOQUEIA HTML
    # --------------------------------------------------

    def test_02_gate_failure_blocks_html(self):

        with (
            patch.object(
                report,
                "validate_persisted_handoff",
                side_effect=PersistentHandoffError(
                    "INTEGRITY_CONFLICT: teste MOCK."
                ),
            ),
            patch.object(
                report,
                "build_report",
            ) as builder,
        ):

            with self.assertRaises(
                PersistentHandoffError
            ):

                report.build_persisted_report(
                    self.source
                )

            builder.assert_not_called()

        print("[OK] Falha do gate bloqueou o HTML.")

    # --------------------------------------------------
    # 03 - VALIDACAO AUSENTE
    # --------------------------------------------------

    def test_03_missing_validation(self):

        with (
            patch.object(
                report,
                "validate_persisted_handoff",
                return_value={},
            ),
            patch.object(
                report,
                "build_report",
            ) as builder,
        ):

            with self.assertRaises(
                report.PersistentReportError
            ):

                report.build_persisted_report(
                    self.source
                )

            builder.assert_not_called()

        print("[OK] Validacao ausente bloqueada.")

    # --------------------------------------------------
    # 04 - METODO DE VERIFICACAO INVALIDO
    # --------------------------------------------------

    def test_04_invalid_verification_method(self):

        contract = valid_contract()

        contract[
            "persistent_handoff_validation"
        ]["verification_method"] = "UNVERIFIED_FIXTURE"

        with (
            patch.object(
                report,
                "validate_persisted_handoff",
                return_value=contract,
            ),
            patch.object(
                report,
                "build_report",
            ) as builder,
        ):

            with self.assertRaises(
                report.PersistentReportError
            ):

                report.build_persisted_report(
                    self.source
                )

            builder.assert_not_called()

        print("[OK] Metodo nao autorizado rejeitado.")

    # --------------------------------------------------
    # 05 - DESPACHO OPERACIONAL INDEVIDO
    # --------------------------------------------------

    def test_05_dispatch_forbidden(self):

        contract = valid_contract()

        contract[
            "persistent_handoff_validation"
        ]["operational_dispatch_allowed"] = True

        with (
            patch.object(
                report,
                "validate_persisted_handoff",
                return_value=contract,
            ),
            patch.object(
                report,
                "build_report",
            ) as builder,
        ):

            with self.assertRaises(
                report.PersistentReportError
            ):

                report.build_persisted_report(
                    self.source
                )

            builder.assert_not_called()

        print("[OK] Despacho operacional bloqueado.")

    # --------------------------------------------------
    # 06 - IDENTIFICADOR POSTGRESQL INVALIDO
    # --------------------------------------------------

    def test_06_invalid_database_id(self):

        contract = valid_contract()

        contract[
            "persistent_handoff_validation"
        ]["database_record_id"] = True

        with (
            patch.object(
                report,
                "validate_persisted_handoff",
                return_value=contract,
            ),
            patch.object(
                report,
                "build_report",
            ) as builder,
        ):

            with self.assertRaises(
                report.PersistentReportError
            ):

                report.build_persisted_report(
                    self.source
                )

            builder.assert_not_called()

        print("[OK] ID PostgreSQL invalido rejeitado.")

    # --------------------------------------------------
    # 07 - GERADOR DEVOLVE HTML VAZIO
    # --------------------------------------------------

    def test_07_empty_html(self):

        with (
            patch.object(
                report,
                "validate_persisted_handoff",
                return_value=valid_contract(),
            ),
            patch.object(
                report,
                "build_report",
                return_value="  ",
            ) as builder,
        ):

            with self.assertRaises(
                report.PersistentReportError
            ):

                report.build_persisted_report(
                    self.source
                )

            builder.assert_called_once()

        print("[OK] HTML vazio rejeitado.")

    # --------------------------------------------------
    # 08 - ERRO DO GERADOR NAO PODE SER OCULTADO
    # --------------------------------------------------

    def test_08_html_builder_exception(self):

        with (
            patch.object(
                report,
                "validate_persisted_handoff",
                return_value=valid_contract(),
            ),
            patch.object(
                report,
                "build_report",
                side_effect=RuntimeError(
                    "Falha controlada no HTML MOCK."
                ),
            ) as builder,
        ):

            with self.assertRaises(RuntimeError):

                report.build_persisted_report(
                    self.source
                )

            builder.assert_called_once()

        print("[OK] Falha do gerador propagada.")


def main():

    print()
    print("=" * 60)
    print(" FASE 13.9.4.3 - TESTES OFFLINE GATE + HTML")
    print("=" * 60)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        PersistentReportTests
    )

    result = unittest.TextTestRunner(
        verbosity=2
    ).run(suite)

    if (
        not result.wasSuccessful()
        or result.testsRun != 8
    ):
        raise RuntimeError(
            "FASE 13.9.4.3 NAO APROVADA."
        )

    print()
    print("=" * 60)
    print(" FASE 13.9.4.3 - VALIDACAO CONCLUIDA")
    print("=" * 60)

    print("Testes aprovados: 8/8")
    print("Gate PostgreSQL: SIMULADO")
    print("Gerador HTML: SIMULADO")
    print("PostgreSQL real: NAO ACIONADO")
    print("Ollama: NAO ACIONADO")
    print("Notificacoes: NENHUMA")
    print("Despacho operacional: BLOQUEADO")
    print()
    print("[OK] INTEGRACAO GATE + HTML VALIDADA OFFLINE")


if __name__ == "__main__":
    main()
