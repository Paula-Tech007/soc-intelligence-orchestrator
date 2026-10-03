"""Phase 09 - Exclusive local guard for one synthetic LAB request.

Coordinates participating workers sharing one local filesystem.
Does NOT reserve or mutate the n8n Data Table.
Does NOT execute a model or perform operational dispatch.
"""

import os
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path

from src.context.n8n_runtime_queue_client import (
    REQUEST_ID,
    fetch_lab_runtime_request,
)


LOCK_PATH = (
    Path(tempfile.gettempdir())
    / "soc-intelligence-orchestrator"
    / "runtime-request-LAB-0001.lock"
)


class LocalClaimBusy(Exception):
    """Another local participant currently holds the guard."""


class LocalClaimError(Exception):
    """The local guard or DRY_RUN contract could not be validated."""


def _lock(handle):
    """Acquire a nonblocking, OS-managed, exclusive file lock."""

    handle.seek(0)

    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)

    elif os.name == "posix":
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    else:
        raise LocalClaimError("Sistema operacional nao suportado.")


def _unlock(handle):
    handle.seek(0)

    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

    elif os.name == "posix":
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def local_request_guard(request_id=REQUEST_ID):
    """Protect one LAB critical section; fail closed on contention."""

    if type(request_id) is not str or request_id != REQUEST_ID:
        raise LocalClaimError("Identificador LAB nao autorizado.")

    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(LOCK_PATH, "a+b") as handle:
        # Windows byte-range locking requires a stable byte at offset zero.
        # The guard's file is persistent; the OS releases its lock on close.
        if os.fstat(handle.fileno()).st_size == 0:
            handle.write(b"\0")
            handle.flush()

        acquired = False

        try:
            try:
                _lock(handle)
                acquired = True
            except OSError as exc:
                import errno

                # Use o codigo nativo do Windows quando disponivel.
                # ERROR_LOCK_VIOLATION = 33.
                winerror = getattr(exc, "winerror", None)

                if winerror is not None:
                    contention = winerror == 33
                else:
                    # Fallback para erros padronizados de bloqueio.
                    # EACCES pode ser ambiguo em algumas plataformas;
                    # independentemente da classificacao, falha fechado.
                    contention = exc.errno in (
                        errno.EACCES,
                        errno.EAGAIN,
                    )

                if contention:
                    raise LocalClaimBusy(
                        "Solicitacao protegida por outro worker local."
                    ) from None

                raise LocalClaimError(
                    "Falha de infraestrutura ao adquirir bloqueio."
                ) from None

            yield

        finally:
            if acquired:
                _unlock(handle)


def run_local_claim_dry_run():
    """Read the existing queue while holding a local exclusive guard.

    A successful result is NOT a Data Table reservation. The lock is
    released before returning to the caller.
    """

    worker_id = str(uuid.uuid4())

    with local_request_guard():
        receipt = fetch_lab_runtime_request()

        if receipt is None:
            return {
                "environment": "LAB",
                "processor": "PYTHON_LOCAL_CLAIM_DRY_RUN",
                "request_available": False,
                "local_guard_completed": True,
                "datatable_reservation_attempted": False,
                "model_execution_started": False,
                "operational_dispatch_allowed": False,
                "notification_sent": False,
                "test_only": True,
            }

        if not isinstance(receipt, dict):
            raise LocalClaimError("Comprovante DRY_RUN invalido.")

        expected = {
            "request_id": REQUEST_ID,
            "source_event_id": "LAB-0001",
            "historical_queue_id": 12,
            "current_queue_id": 13,
            "status": "QUEUED",
            "execution_mode": "DRY_RUN",
            "human_review_required": True,
            "human_review_completed": False,
            "model_execution_started": False,
            "table_mutation_attempted": False,
            "operational_dispatch_allowed": False,
            "notification_sent": False,
        }

        for field, value in expected.items():
            received = receipt.get(field)

            if type(received) is not type(value) or received != value:
                raise LocalClaimError(
                    "Contrato DRY_RUN divergente: " + field
                )

        row_id = receipt.get("row_id")

        if type(row_id) is not int or row_id < 1:
            raise LocalClaimError("ID da linha fora do contrato.")

        return {
            "schema_version": "1.0",
            "environment": "LAB",
            "processor": "PYTHON_LOCAL_CLAIM_DRY_RUN",
            "request_id": REQUEST_ID,
            "worker_id": worker_id,
            "row_id": row_id,
            "local_guard_completed": True,
            "datatable_reservation_attempted": False,
            "status_observed": "QUEUED",
            "model_execution_started": False,
            "operational_dispatch_allowed": False,
            "notification_sent": False,
            "test_only": True,
        }