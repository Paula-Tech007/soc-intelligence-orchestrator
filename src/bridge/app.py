"""
SOC Intelligence Orchestrator
Local PostgreSQL Bridge - LAB

API HTTP exclusivamente local e de leitura.
Nao executa IA, nao altera filas e nao envia notificacoes.
"""

from fastapi import FastAPI, HTTPException, Path

from src.context.context_builder import build_context
from src.bridge.db import connect_bridge_db


app = FastAPI(
    title="SOC Intelligence Orchestrator - Local Bridge",
    version="0.1.0",
    description="Ponte local para contextos sinteticos do LAB.",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/health")
def health():
    """
    Verifica se a API esta respondendo.

    Nao consulta o banco de dados.
    """
    return {
        "service": "soc-local-postgres-bridge",
        "environment": "LAB",
        "status": "UP",
        "database_checked": False,
        "operational_dispatch_allowed": False,
    }


@app.get("/lab/context/{queue_id}")
def get_lab_context(
    queue_id: int = Path(ge=1, le=2147483647),
):
    """
    Consulta um contexto ja existente.

    Reutiliza o WF-03 sem criar novas investigacoes,
    ocorrencias, versoes ou tarefas.
    """

    try:
        context = build_context(
            queue_id,
            connection_factory=connect_bridge_db,
        )

    except LookupError:
        raise HTTPException(
            status_code=404,
            detail="Contexto LAB nao encontrado.",
        ) from None

    except Exception:
        # Nao retornar mensagens internas do PostgreSQL
        # nem detalhes de conexao ao consumidor HTTP.
        raise HTTPException(
            status_code=503,
            detail="Consulta LAB indisponivel.",
        ) from None

    if context is None:
        raise HTTPException(
            status_code=404,
            detail="Contexto LAB nao encontrado.",
        )

    if (
        not isinstance(context, dict)
        or context.get("environment") != "LAB"
        or context.get("processor") != "WF-03"
        or context.get("queue_id") != queue_id
        or context.get("dispatch_status") != "MOCK_ONLY"
        or context.get("notification_sent") is not False
        or context.get("ai_executed") is not False
    ):
        raise HTTPException(
            status_code=409,
            detail="Contrato de contexto nao autorizado.",
        )

    return {
        "integration_mode": "LOCAL_POSTGRES_READ_ONLY",
        "real_database_query": True,
        "operational_dispatch_allowed": False,
        "human_review_required": True,
        "context": context,
    }