import copy
import json
import uuid

from pathlib import Path
from psycopg.rows import tuple_row

import src.ai_engine.integrity_persistence as persistence

from src.ai_engine.integrity import build_integrity_record
from src.dedup.persistence import connect_db as real_connect_db
from src.reports.report_builder import validate_contract


class InjectedFailure(RuntimeError):
    pass


state = {
    "insert_observed": False,
    "inserted_id": None,
}


def snapshot():

    with real_connect_db() as conn:

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


class InterceptCursor:

    def __init__(self, cursor):
        self.cursor_real = cursor
        self.is_insert = False

    def __enter__(self):
        self.cursor_real.__enter__()
        return self

    def __exit__(self, *args):
        return self.cursor_real.__exit__(*args)

    def execute(self, sql, params=None):

        self.is_insert = (
            "INSERT INTO PUBLIC.AI_ANALYSIS_INTEGRITY"
            in " ".join(sql.upper().split())
        )

        return self.cursor_real.execute(sql, params)

    def fetchone(self):

        result = self.cursor_real.fetchone()

        if self.is_insert and result is not None:

            state["insert_observed"] = True
            state["inserted_id"] = result[0]

            raise InjectedFailure(
                "Falha intencional imediatamente apos INSERT."
            )

        return result

    def __getattr__(self, name):
        return getattr(self.cursor_real, name)


class InterceptConnection:

    def __init__(self, conn):
        self.conn_real = conn

    def __enter__(self):
        self.conn_real.__enter__()
        return self

    def __exit__(self, *args):
        return self.conn_real.__exit__(*args)

    def cursor(self, *args, **kwargs):

        return InterceptCursor(
            self.conn_real.cursor(*args, **kwargs)
        )

    def transaction(self, *args, **kwargs):
        return self.conn_real.transaction(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.conn_real, name)


print()
print("=" * 58)
print(" FASE 13.7.12.4 - FALHA INJETADA NA PERSISTENCIA")
print("=" * 58)

root = Path(__file__).resolve().parents[1]

fixture = root / "tests/fixtures/wf04_wf05_integrity_mock.json"

envelope = json.loads(
    fixture.read_text(encoding="utf-8-sig")
)

_, current = validate_contract(envelope)

result = copy.deepcopy(current)

result.update({
    "fixture_type": "MOCK_AI_RESPONSE",
    "real_ollama_call": False,
    "ready_for_operational_dispatch": False,
    "model": "rollback-injected-mock-" + uuid.uuid4().hex,
})

record = build_integrity_record(result)

# ----------------------------------------------------------
# 1. PREFLIGHT
# ----------------------------------------------------------

before = snapshot()

assert len(before) == 2, (
    "Esperados dois registros antes do teste."
)

assert [row[0] for row in before] == [1, 9]

assert all(row[12] is False for row in before)

assert not any(
    row[9] == record["result_key"]
    for row in before
)

print()
print("=== 1. PREFLIGHT ===")
print("[OK] Dois registros originais conferidos.")
print("[OK] Identidade do teste ainda inexistente.")

# ----------------------------------------------------------
# 2. INJETAR FALHA NA FUNCAO REAL
# ----------------------------------------------------------

original_factory = persistence.connect_db

def intercepted_factory():

    return InterceptConnection(
        real_connect_db()
    )

error_captured = False

try:

    persistence.connect_db = intercepted_factory

    try:

        persistence.persist_integrity_record(record)

    except InjectedFailure:

        error_captured = True

finally:

    persistence.connect_db = original_factory

assert state["insert_observed"], (
    "O INSERT nao foi executado. Teste inconclusivo."
)

assert state["inserted_id"] is not None

assert error_captured, (
    "A falha intencional nao foi capturada."
)

print()
print("=== 2. FALHA CONTROLADA ===")
print("[OK] INSERT executado pelo modulo real.")
print("[OK] Falha provocada apos o INSERT.")
print("[OK] Excecao propagada para fora da transacao.")
print("[OK] Interceptador temporario restaurado.")

# ----------------------------------------------------------
# 3. VERIFICACAO DO BANCO
# ----------------------------------------------------------

after = snapshot()

assert before == after, (
    "FALHA CRITICA: o estado do PostgreSQL foi alterado."
)

assert len(after) == 2

assert not any(
    row[9] == record["result_key"]
    for row in after
)

print()
print("=== 3. VERIFICACAO FINAL ===")
print("[OK] INSERT desfeito pelo rollback.")
print("[OK] Registro temporario nao existe.")
print("[OK] Dois registros originais preservados.")
print("[OK] Assinaturas permanecem inalteradas.")
print("[OK] Despacho operacional desabilitado.")

print()
print("=" * 58)
print(" FASE 13.7.12.4 - ROLLBACK DA FUNCAO VALIDADO")
print("=" * 58)

print("Registros antes:", len(before))
print("Registros depois:", len(after))
print("Persistencia indevida: NENHUMA")
print("Ollama: NAO ACIONADO")
print("Notificacoes: NENHUMA")

print()
print("[OK] FASE 13.7.12.4 APROVADA")
