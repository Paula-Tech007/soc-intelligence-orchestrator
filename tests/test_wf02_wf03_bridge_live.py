"""
FASE 14.3.2.5 - Integracao WF-01 / WF-02 / WF-03.

Executa os Code Nodes reais do workflow integrado
com Node.js e encaminha seus resultados ao Python.

PostgreSQL: somente consultas.
Nenhuma execucao de process_event().
"""

import copy
import hashlib
import json
import subprocess
import sys

from pathlib import Path
from unittest.mock import patch

from psycopg.rows import tuple_row

import src.context.wf02_wf03_bridge as bridge

from src.dedup.persistence import connect_db


ROOT = Path(__file__).resolve().parents[1]

WORKFLOW = ROOT / (
    "workflows/INTEGRACAO-WF01-WF02-LAB.json"
)

ORIGINALS = [
    ROOT / "workflows/WF-01-Coleta-de-Eventos.json",
    ROOT / "workflows/WF-02-Normalizacao-e-Deduplicacao.json",
    ROOT / "workflows/WF-03-Contexto-e-Correlacao.json",
    WORKFLOW,
]

TABLES = (
    "investigations",
    "investigation_versions",
    "evidences",
    "event_occurrences",
    "analysis_queue",
    "audit_log",
    "ai_analysis_integrity",
)


def check(condition, description):

    if not condition:
        raise AssertionError("FALHA: " + description)

    print("[OK]", description, flush=True)


def file_hash(path):

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def database_snapshot():
    """
    Fotografia integral das sete tabelas LAB.
    Executa apenas SELECT.
    """

    result = {}

    with connect_db() as conn:

        with conn.cursor(row_factory=tuple_row) as cur:

            for table in TABLES:

                # table vem exclusivamente da constante TABLES.
                cur.execute(
                    f"""
                    SELECT to_jsonb(t)
                    FROM public.{table} AS t
                    ORDER BY t.id;
                    """
                )

                result[table] = [
                    row[0] for row in cur.fetchall()
                ]

    return result


NODE_RUNNER = r"""
const fs = require("node:fs");
const vm = require("node:vm");

const workflow = JSON.parse(
  fs.readFileSync(
    "workflows/INTEGRACAO-WF01-WF02-LAB.json",
    "utf8"
  )
);

if (
  workflow.active !== false ||
  workflow.nodes.length !== 7
) {
  throw new Error("Workflow LAB inesperado.");
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function execute(name, items) {

  const found = workflow.nodes.filter(
    n => n.name === name
  );

  if (found.length !== 1) {
    throw new Error("No nao identificado: " + name);
  }

  const code = found[0].parameters.jsCode;

  const input = clone(items);

  const output = vm.runInNewContext(
    "(function(){\n" + code + "\n})()",
    {
      $input: {
        all: () => input,
        first: () => input[0]
      },
      Date,
      JSON,
      Map,
      Set,
      Error,
      Array,
      Object,
      String,
      Number,
      Boolean,
      Math
    },
    {
      timeout: 3000,
      filename: name
    }
  );

  if (!Array.isArray(output)) {
    throw new Error("Saida JS invalida: " + name);
  }

  return clone(output);
}

let items = [{json: {}}];

const sequence = [
  "01 - Coletar Eventos Sinteticos",
  "02 - Validar Eventos",
  "03 - Preparar Entrega ao WF-02",
  "04 - Adaptar Contrato WF-01 para WF-02",
  "02 - Normalizar e Deduplicar",
  "03 - Validar Decisoes e Auditoria"
];

for (const name of sequence) {
  items = execute(name, items);
}

process.stdout.write(
  JSON.stringify(items.map(item => item.json))
);
"""


def get_real_wf02_output():

    execution = subprocess.run(
        ["node", "-e", NODE_RUNNER],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    if execution.returncode != 0:

        raise RuntimeError(
            "Falha na execucao dos Code Nodes JS:\n"
            + execution.stderr
        )

    result = json.loads(execution.stdout)

    if not isinstance(result, list):
        raise ValueError("Saida WF-02 nao e uma lista.")

    return result


print()
print("=" * 64)
print(" FASE 14.3.2.5 - INTEGRACAO JS / PYTHON / POSTGRESQL")
print("=" * 64)

for filename in ORIGINALS:

    if not filename.is_file():
        raise FileNotFoundError(str(filename))

hashes = {
    filename: file_hash(filename)
    for filename in ORIGINALS
}

before = database_snapshot()

check(
    len(before["ai_analysis_integrity"]) == 2
    and [
        row["id"]
        for row in before["ai_analysis_integrity"]
    ] == [1, 9],
    "Registros originais de integridade encontrados.",
)

print()
print("=== 1. EXECUTAR WF-01 E WF-02 EM NODE.JS ===")

try:

    items = get_real_wf02_output()

    check(
        len(items) == 3,
        "Tres resultados reais dos Code Nodes recebidos.",
    )

    expected = (
        ("NEW_EVENT", True, 1),
        ("EXACT_REPEAT", False, 1),
        ("MATERIAL_UPDATE", True, 2),
    )

    for index, (status, analyze, version) in enumerate(
        expected
    ):

        item = items[index]

        check(
            item["deduplication"]["status"] == status
            and item["decision"]["should_analyze"] is analyze
            and item["deduplication"][
                "investigation_version"
            ] == version,
            f"WF-02 evento {index + 1}: {status}.",
        )

    print()
    print("=== 2. TESTES NEGATIVOS ANTES DO BANCO ===")

    # O primeiro teste adultera a assinatura canonica.
    tampered_signature = copy.deepcopy(items)

    tampered_signature[0]["content_signature"] = "{}"

    with patch.object(
        bridge,
        "connect_db",
        side_effect=AssertionError(
            "O banco nao deveria ser acionado."
        ),
    ) as guarded_db:

        try:

            bridge.resolve_existing_contexts(
                tampered_signature
            )

        except bridge.ContextBridgeError:
            print(
                "[OK] Conteudo canonico adulterado bloqueado."
            )

        else:
            raise AssertionError(
                "Assinatura adulterada foi aceita."
            )

        guarded_db.assert_not_called()

    # O segundo teste altera o ambiente autorizado.
    tampered_environment = copy.deepcopy(items)

    tampered_environment[1]["environment"] = "PROD"

    with patch.object(
        bridge,
        "connect_db",
        side_effect=AssertionError(
            "O banco nao deveria ser acionado."
        ),
    ) as guarded_db:

        try:

            bridge.resolve_existing_contexts(
                tampered_environment
            )

        except bridge.ContextBridgeError:
            print(
                "[OK] Ambiente nao autorizado bloqueado."
            )

        else:
            raise AssertionError(
                "Ambiente adulterado foi aceito."
            )

        guarded_db.assert_not_called()

    print()
    print("=== 3. EXECUTAR A PONTE REAL ===")

    # A partir daqui a ponte utiliza apenas SELECT.
    result = bridge.resolve_existing_contexts(items)

    check(
        result["environment"] == "LAB"
        and result["processor"] == "WF02-WF03-BRIDGE"
        and result["persistence_action"] == "READ_ONLY_LOOKUP"
        and result["runtime_database_query"] is True,
        "Contrato da ponte retornado corretamente.",
    )

    contexts = result["contexts"]
    skipped = result["skipped"]

    check(
        len(contexts) == 2
        and [entry["queue_id"] for entry in contexts]
        == [12, 13],
        "Filas persistidas 12 e 13 recuperadas.",
    )

    historical = contexts[0]["context"]
    current = contexts[1]["context"]

    check(
        historical["requested_version"] == 1
        and historical["current_version"] == 2
        and historical["is_historical_version"] is True
        and historical["eligible_for_context_review"] is False
        and historical["context_status"]
        == "HISTORICAL_VERSION",
        "Versao historica corretamente bloqueada.",
    )

    check(
        current["requested_version"] == 2
        and current["current_version"] == 2
        and current["is_historical_version"] is False
        and current["eligible_for_context_review"] is True
        and current["context_status"] == "READY_FOR_REVIEW",
        "Versao atual elegivel para revisao.",
    )

    check(
        len(skipped) == 1
        and skipped[0]["source_case"] == "EXACT_REPEAT"
        and skipped[0]["reason"] == "NO_NEW_ANALYSIS",
        "Repeticao exata suprimida.",
    )

    check(
        historical["investigation_id"]
        == current["investigation_id"]
        and result["real_execution_started"] is False
        and result["notification_sent"] is False
        and result["operational_dispatch_allowed"] is False,
        "Mesma investigacao e despacho operacional bloqueado.",
    )

finally:

    print()
    print("=== 4. CONFERENCIA FINAL DO AMBIENTE ===")

    after = database_snapshot()

    check(
        before == after,
        "Sete tabelas PostgreSQL integralmente preservadas.",
    )

    for filename, initial_hash in hashes.items():

        check(
            file_hash(filename) == initial_hash,
            "Arquivo original preservado: " + filename.name,
        )


print()
print("=" * 64)
print(" FASE 14.3.2.5 - INTEGRACAO APROVADA")
print("=" * 64)

print("Resultados JS recebidos:", len(items))
print("Contextos PostgreSQL recuperados:", len(contexts))
print("Filas:", [entry["queue_id"] for entry in contexts])
print("Repeticoes suprimidas:", len(skipped))
print("Tabelas conferidas:", len(TABLES))
print("process_event(): NAO EXECUTADO")
print("PostgreSQL: SOMENTE SELECT")
print("Ollama: NAO ACIONADO")
print("n8n remoto: NAO ACIONADO")
print("Despacho operacional: BLOQUEADO")
print("Git: SEM COMMIT / SEM PUSH")

print()
print("[OK] WF-01 -> WF-02 -> POSTGRESQL -> WF-03 VALIDADO")
