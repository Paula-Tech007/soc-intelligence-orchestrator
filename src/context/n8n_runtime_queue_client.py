"""Phase 09 - Read-only authenticated n8n LAB request consumer.

DRY_RUN only. No model execution, row updates or dispatch.
"""

import os

import httpx


QUEUE_URL = (
    "http://127.0.0.1:5679"
    "/webhook/soc-lab-runtime-queue-read"
)

REQUEST_ID = "SOC-LAB-0001-Q12-Q13"


class QueueClientError(Exception):
    """Controlled n8n LAB transport or contract failure."""


def fetch_lab_runtime_request():
    """Return the validated LAB fixture or None when the queue is empty."""

    token = os.environ.get("SOC_N8N_LAB_HEADER_KEY", "")

    if not isinstance(token, str) or len(token) < 32:
        raise QueueClientError("Credencial n8n LAB indisponivel.")

    try:
        response = httpx.get(
            QUEUE_URL,
            headers={"X-SOC-LAB-KEY": token},
            timeout=5.0,
            follow_redirects=False,
            trust_env=False,
        )
    except httpx.RequestError:
        raise QueueClientError(
            "Consulta HTTP ao n8n LAB indisponivel."
        ) from None

    if response.status_code != 200:
        raise QueueClientError(
            "Consulta n8n LAB recusada. HTTP "
            + str(response.status_code)
            + "."
        )

    try:
        receipt = response.json()
    except (ValueError, TypeError):
        raise QueueClientError("Comprovante JSON invalido.") from None

    if not isinstance(receipt, dict):
        raise QueueClientError("Envelope de consulta invalido.")

    expected = {
        "schema_version": "1.0",
        "environment": "LAB",
        "processor": "N8N_RUNTIME_QUEUE_READ",
        "test_only": True,
        "operational_dispatch_allowed": False,
        "notification_sent": False,
        "human_review_required": True,
        "human_review_completed": False,
    }

    for key, value in expected.items():
        received = receipt.get(key)

        if type(received) is not type(value) or received != value:
            raise QueueClientError(
                "Contrato de seguranca divergente: " + key
            )

    status = receipt.get("transport_status")

    if status == "NO_QUEUED_REQUEST":
        if receipt.get("request_available") is not False:
            raise QueueClientError("Estado vazio inconsistente.")
        return None

    if status != "QUEUED_REQUEST_AVAILABLE":
        raise QueueClientError("Estado de transporte nao autorizado.")

    fixture = {
        "request_available": True,
        "request_id": REQUEST_ID,
        "source_event_id": "LAB-0001",
        "historical_queue_id": 12,
        "current_queue_id": 13,
        "status": "QUEUED",
        "execution_mode": "LAB_TEST_ONLY",
    }

    for key, value in fixture.items():
        received = receipt.get(key)

        if type(received) is not type(value) or received != value:
            raise QueueClientError(
                "Solicitacao LAB fora do contrato: " + key
            )

    row_id = receipt.get("row_id")

    if type(row_id) is not int or row_id < 1:
        raise QueueClientError("Identificador de linha invalido.")

    # Explicit allowlist: never forward unexpected response fields.
    return {
        "schema_version": "1.0",
        "environment": "LAB",
        "processor": "PYTHON_N8N_QUEUE_DRY_RUN",
        "request_id": REQUEST_ID,
        "row_id": row_id,
        "source_event_id": "LAB-0001",
        "historical_queue_id": 12,
        "current_queue_id": 13,
        "status": "QUEUED",
        "execution_mode": "DRY_RUN",
        "human_review_required": True,
        "human_review_completed": False,
        "model_execution_started": False,
        "operational_dispatch_allowed": False,
        "notification_sent": False,
        "table_mutation_attempted": False,
    }