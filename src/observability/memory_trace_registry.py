"""
Stage 16 - Registro idempotente de rastreabilidade em memoria.

Simulacao local de NEW_RESULT, ALREADY_REGISTERED e
INTEGRITY_CONFLICT, sem utilizar PostgreSQL.

Nao fornece comprovante de persistencia.
Cada instancia possui armazenamento privado e temporario.
"""

import copy
import re

from src.ai_engine.integrity import sha256_json
from src.observability.persistence_traceability import (
    build_memory_traceability,
)


class MemoryTraceConflictError(ValueError):
    """Identidade logica ou result_key com metadados divergentes."""


class MemoryTraceRegistry:
    """Registro temporario, deterministico e restrito ao LAB/MOCK."""

    _FIELDS = frozenset({
        "schema_version",
        "environment",
        "processor",
        "integration_mode",
        "identity",
        "historical_control",
        "content_signature",
        "analysis_signature",
        "result_key",
        "integrity_status",
        "persistence_status",
        "database_record_id",
        "verification_method",
        "verified_against_database",
        "human_review_required",
        "operational_dispatch_allowed",
        "notification_sent",
    })

    _IDENTITY_FIELDS = frozenset({
        "environment",
        "investigation_id",
        "source_event_id",
        "queue_id",
        "investigation_version",
        "content_signature",
        "model",
        "execution_mode",
    })

    def __init__(self):
        self._records = {}
        self._by_result_key = {}

    @classmethod
    def _validate(cls, trace, *, generic=False):
        if not isinstance(trace, dict):
            raise ValueError("Rastreabilidade invalida.")

        if set(trace) != cls._FIELDS:
            raise ValueError("Campos de rastreabilidade divergentes.")

        expected = {
            "schema_version": "1.0",
            "environment": "LAB",
            "processor": "WF-05-TRACEABILITY",
            "integration_mode": "IN_MEMORY_MOCK",
            "integrity_status": "VERIFIED_IN_MEMORY",
            "persistence_status": "NOT_ATTEMPTED",
            "database_record_id": None,
            "verification_method": "SHA256_IN_MEMORY",
            "verified_against_database": False,
            "human_review_required": True,
            "operational_dispatch_allowed": False,
            "notification_sent": False,
        }

        for field, value in expected.items():
            if trace.get(field) != value or (
                isinstance(value, bool)
                and trace.get(field) is not value
            ):
                raise ValueError("Estado invalido: " + field)

        identity = trace["identity"]

        if (
            not isinstance(identity, dict)
            or set(identity) != cls._IDENTITY_FIELDS
        ):
            raise ValueError("Identidade logica invalida.")

        if (
            identity.get("environment") != "LAB"
            or identity.get("execution_mode") != "MOCK_AI_RESPONSE"
            or type(identity.get("queue_id")) is not int
            or identity["queue_id"] < 1
            or (not generic and identity["queue_id"] != 13)
            or type(identity.get("investigation_version")) is not int
            or identity["investigation_version"] < 1
            or (
                not generic
                and identity["investigation_version"] != 2
            )
        ):
            raise ValueError("Identidade fora do escopo LAB.")

        for field in (
            "investigation_id",
            "source_event_id",
            "model",
        ):
            value = identity.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Identificacao invalida: " + field)

        if (
            not generic
            and identity["source_event_id"] != "LAB-0001"
        ):
            raise ValueError("Evento fora do contrato homologado.")

        historical = trace["historical_control"]

        legacy_historical = {
            "queue_id": 12,
            "investigation_version": 1,
            "status": "SKIPPED",
            "ai_executed": False,
        }

        if generic:
            if (
                type(historical) is not dict
                or set(historical) != set(legacy_historical)
                or type(historical.get("queue_id")) is not int
                or historical["queue_id"] < 1
                or historical["queue_id"] == identity["queue_id"]
                or type(historical.get("investigation_version"))
                is not int
                or historical["investigation_version"] < 1
                or historical["investigation_version"] + 1
                != identity["investigation_version"]
                or historical.get("status") != "SKIPPED"
                or historical.get("ai_executed") is not False
            ):
                raise ValueError("Generic historical control mismatch.")

        elif historical != legacy_historical:
            raise ValueError("Controle historico divergente.")

        for field in (
            "content_signature",
            "analysis_signature",
            "result_key",
        ):
            signature = trace.get(field)

            if (
                not isinstance(signature, str)
                or re.fullmatch(r"[a-f0-9]{64}", signature) is None
            ):
                raise ValueError("Assinatura invalida: " + field)

        if (
            trace["content_signature"]
            != identity["content_signature"]
            or trace["result_key"] != sha256_json(identity)
        ):
            raise ValueError("Identidade e assinaturas divergentes.")

        # A assinatura da analise ja foi verificada pelo adaptador
        # anterior. Este registro nao recebe a analise original.
        return identity

    def register(
        self,
        trace,
        *,
        trusted_contract=None,
        integrity_record=None,
        expected_evidence_ids=None,
    ):
        """
        Registra metadados validados somente em memoria.

        MEMORY_NEW_RESULT: primeira inclusao.
        MEMORY_ALREADY_REGISTERED: repeticao integralmente identica.

        Uma identidade logica ou result_key com conteudo
        divergente provoca INTEGRITY_CONFLICT, sem sobrescrita.
        """
        generic = any(
            value is not None
            for value in (
                trusted_contract,
                integrity_record,
                expected_evidence_ids,
            )
        )

        if generic:
            if any(
                value is None
                for value in (
                    trusted_contract,
                    integrity_record,
                    expected_evidence_ids,
                )
            ):
                raise ValueError(
                    "Generic registration requires complete trust inputs."
                )

            # Independently rebuild the expected trace using the
            # official WF-05 contract and original SHA-256 record.
            expected_trace = build_memory_traceability(
                trusted_contract,
                integrity_record,
                expected_evidence_ids=expected_evidence_ids,
            )

            if trace != expected_trace:
                raise ValueError(
                    "Trace does not match independently verified input."
                )

        identity = self._validate(trace, generic=generic)

        logical_key = (
            identity["environment"],
            identity["investigation_id"],
            identity["investigation_version"],
            identity["model"],
            identity["execution_mode"],
        )

        result_key = trace["result_key"]

        existing = self._records.get(logical_key)
        existing_key = self._by_result_key.get(result_key)

        if existing is not None or existing_key is not None:
            if (
                existing is not None
                and existing_key == logical_key
                and existing == trace
            ):
                status = "MEMORY_ALREADY_REGISTERED"
            else:
                raise MemoryTraceConflictError(
                    "INTEGRITY_CONFLICT: identidade logica "
                    "ou result_key com metadados divergentes."
                )
        else:
            self._records[logical_key] = copy.deepcopy(trace)
            self._by_result_key[result_key] = logical_key
            status = "MEMORY_NEW_RESULT"

        return {
            "status": status,
            "result_key": result_key,
            "analysis_signature": trace["analysis_signature"],
            "integrity_status": "VERIFIED_IN_MEMORY",
            "persistence_status": "NOT_ATTEMPTED",
            "database_record_id": None,
            "verified_against_database": False,
            "operational_dispatch_allowed": False,
        }

    def count(self):
        """Quantidade de registros temporarios desta instancia."""
        return len(self._records)
