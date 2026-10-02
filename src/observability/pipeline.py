"""
Etapa 14 - Instrumentacao opcional do pipeline SOC-LAB.

O pipeline integrado original nao e modificado.

A telemetria permanece local e em memoria, usando somente
os campos autorizados pelo coletor.

Nao captura mensagens brutas de excecoes.
Nao envia eventos para servicos externos.
"""

from time import perf_counter_ns

from src.context.integrated_mock_pipeline import (
    run_integrated_mock_review,
)

from src.observability.collector import (
    collect_review_telemetry,
)


def run_observed_mock_review(queue_id: int, *, cache=None):
    """
    Executa o pipeline existente e mede sua duracao.

    Retorno:
        {
            "result": resultado_original,
            "telemetry": resumo_sanitizado
        }

    Falhas do pipeline sao propagadas sem conversao em sucesso.
    Nenhuma referencia ao contexto original entra na telemetria.
    """

    started_ns = perf_counter_ns()

    result = run_integrated_mock_review(
        queue_id,
        cache=cache,
    )

    finished_ns = perf_counter_ns()

    elapsed_ns = max(0, finished_ns - started_ns)
    duration_ms = elapsed_ns // 1_000_000

    telemetry = collect_review_telemetry(
        result,
        duration_ms=duration_ms,
    )

    return {
        "result": result,
        "telemetry": telemetry,
    }
