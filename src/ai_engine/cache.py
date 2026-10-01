"""
WF-04 - Cache em memoria para testes LAB/MOCK.

Nao consulta banco, nao persiste resultados e nao executa
chamadas externas por conta propria.

Uma nova versao exige nova analise.
Mudanca silenciosa no conteudo da mesma versao e bloqueada.
"""

import copy
import hashlib
import json

from src.ai_engine.engine import analyze, validate_context


class AnalysisCache:

    def __init__(self):
        self._results = {}
        self._seen_versions = {}

    @staticmethod
    def _digest(value):
        content = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

        return hashlib.sha256(content).hexdigest()

    def run_mock(self, context, model, model_id="FAKE_MODEL"):

        # Nunca buscar cache antes de validar o contrato.
        validation = validate_context(context)

        if model is None:
            raise ValueError(
                "FASE MOCK exige modelo simulado explicito."
            )

        if not isinstance(model_id, str) or not model_id:
            raise ValueError("Identificador do modelo invalido.")

        # Historicos continuam bloqueados, mesmo se
        # algum resultado anterior existir em memoria.
        if not validation["eligible"]:

            result = analyze(context, model=model)

            return {
                **copy.deepcopy(result),
                "cache_hit": False,
                "model_invoked_this_call": False,
            }

        identity = (
            context["investigation_id"],
            context["source_event_id"],
            context["requested_version"],
        )

        signature = context["provenance"]["content_signature"]

        digest = self._digest(context)

        version_fingerprint = (signature, digest)

        previous = self._seen_versions.get(identity)

        if previous is not None and previous != version_fingerprint:
            raise ValueError(
                "Conflito: mesma investigacao e versao "
                "com assinatura ou contexto diferente."
            )

        key = (
            identity,
            signature,
            digest,
            model_id,
            "MOCK",
        )

        if key in self._results:

            return {
                **copy.deepcopy(self._results[key]),
                "cache_hit": True,
                "model_invoked_this_call": False,
            }

        # Chamamos o motor existente, sem duplicar sua
        # logica de validacao de JSON e evidencias.
        result = analyze(context, model=model)

        if result["status"] != "ANALYSIS_COMPLETED":
            raise RuntimeError("Resultado inesperado do motor.")

        self._seen_versions[identity] = version_fingerprint

        self._results[key] = copy.deepcopy(result)

        return {
            **copy.deepcopy(result),
            "cache_hit": False,
            "model_invoked_this_call": True,
        }
