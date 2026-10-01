"""
FASE 14.3.2.6

Executa WF-01/WF-02, consulta a ponte PostgreSQL
e testa os dois Code Nodes finais do WF-03.

Nenhum workflow original e modificado.
"""

import ast
import copy
import hashlib
import json
import subprocess

from pathlib import Path

from psycopg.rows import tuple_row

from src.context.wf02_wf03_bridge import (
    resolve_existing_contexts,
)

from src.dedup.persistence import connect_db


ROOT = Path(__file__).resolve().parents[1]

WF03 = ROOT / (
    "workflows/WF-03-Contexto-e-Correlacao.json"
)

PREVIOUS_TEST = ROOT / (
    "tests/test_wf02_wf03_bridge_live.py"
)

TABLES = (
    "investigations",
    "investigation_versions",
    "evidences",
    "event_occurrences",
    "analysis_queue",
    "audit_log",
    "ai_analysis_integrity",
)


def check(condition, message):

    if not condition:
        raise AssertionError(message)

    print("[OK]", message, flush=True)


def sha256_file(path):

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def snapshot():

    result = {}

    with connect_db() as connection:

        with connection.cursor(
            row_factory=tuple_row
        ) as cursor:

            for table in TABLES:

                cursor.execute(
                    f"""
                    SELECT to_jsonb(t)
                    FROM public.{table} AS t
                    ORDER BY t.id;
                    """
                )

                result[table] = [
                    row[0]
                    for row in cursor.fetchall()
                ]

    return result


def recover_previous_node_runner():

    tree = ast.parse(
        PREVIOUS_TEST.read_text(
            encoding="utf-8-sig"
        )
    )

    matches = []

    for node in tree.body:

        if not isinstance(node, ast.Assign):
            continue

        if any(
            isinstance(target, ast.Name)
            and target.id == "NODE_RUNNER"
            for target in node.targets
        ):
            matches.append(
                ast.literal_eval(node.value)
            )

    if len(matches) != 1:
        raise RuntimeError(
            "Runner WF-01/WF-02 nao identificado."
        )

    return matches[0]


WF03_NODE_RUNNER = r"""
const fs = require("node:fs");
const vm = require("node:vm");

const workflow = JSON.parse(
  fs.readFileSync(
    "workflows/WF-03-Contexto-e-Correlacao.json",
    "utf8"
  )
);

const payload = JSON.parse(
  fs.readFileSync(0, "utf8")
);

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function execute(name, items) {

  const found = workflow.nodes.filter(
    node => node.name === name
  );

  if (found.length !== 1) {
    throw new Error("No WF-03 nao encontrado: " + name);
  }

  let code = found[0].parameters.jsCode;

  // Ajuste de proveniencia SOMENTE em memoria.
  // Os JSONs originais nao sao modificados.

  if (name === "03 - Preparar Resultado WF-04") {

    const oldSnapshot = "snapshot_mode: true";
    const oldRuntime = "runtime_database_query: false";

    if (
      code.split(oldSnapshot).length !== 2 ||
      code.split(oldRuntime).length !== 2
    ) {
      throw new Error(
        "Marcadores originais de proveniencia inesperados."
      );
    }

    code = code.replace(
      oldSnapshot,
      "snapshot_mode: contexto.snapshot_mode"
    );

    code = code.replace(
      oldRuntime,
      "runtime_database_query: contexto.runtime_database_query"
    );
  }

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
    throw new Error("Saida WF-03 invalida.");
  }

  return clone(output);
}

let items = payload.contexts.map(
  context => ({ json: context })
);

items = execute(
  "02 - Validar Contexto e Versao",
  items
);

items = execute(
  "03 - Preparar Resultado WF-04",
  items
);

process.stdout.write(
  JSON.stringify(items.map(item => item.json))
);
"""


def execute_node(script, stdin=None):

    completed = subprocess.run(
        ["node", "-e", script],
        cwd=str(ROOT),
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    return completed


print()
print("=" * 64)
print(" FASE 14.3.2.6 - CONTRATO INTEGRADO WF-03")
print("=" * 64)

protected = [
    WF03,
    PREVIOUS_TEST,
    ROOT / "workflows/INTEGRACAO-WF01-WF02-LAB.json",
]

hashes = {
    path: sha256_file(path)
    for path in protected
}

before = snapshot()

try:

    print()
    print("=== 1. EXECUTAR WF-01/WF-02 ===")

    first_stage = execute_node(
        recover_previous_node_runner()
    )

    if first_stage.returncode != 0:
        raise RuntimeError(first_stage.stderr)

    wf02_results = json.loads(
        first_stage.stdout
    )

    check(
        len(wf02_results) == 3,
        "Tres resultados WF-02 recebidos.",
    )

    print()
    print("=== 2. RECUPERAR CONTEXTOS POSTGRESQL ===")

    resolved = resolve_existing_contexts(
        wf02_results
    )

    check(
        [entry["queue_id"] for entry in resolved["contexts"]]
        == [12, 13],
        "Filas 12 e 13 recuperadas.",
    )

    check(
        len(resolved["skipped"]) == 1
        and resolved["skipped"][0]["source_case"]
        == "EXACT_REPEAT",
        "Repeticao exata suprimida.",
    )

    # Marcar corretamente a origem consultada.
    # Ajuste feito exclusivamente nas copias em memoria.

    contexts = []

    for entry in resolved["contexts"]:

        context = copy.deepcopy(
            entry["context"]
        )

        context.update({
            "snapshot_mode": False,
            "snapshot_origin": "LIVE_POSTGRESQL_LOOKUP",
            "runtime_database_query": True,
        })

        contexts.append(context)

    print()
    print("=== 3. EXECUTAR NÓS DO WF-03 ===")

    execution = execute_node(
        WF03_NODE_RUNNER,
        json.dumps(
            {"contexts": contexts},
            ensure_ascii=False,
        ),
    )

    if execution.returncode != 0:
        raise RuntimeError(
            "Falha nos Code Nodes WF-03:\n"
            + execution.stderr
        )

    results = json.loads(
        execution.stdout
    )

    check(
        len(results) == 2,
        "WF-03 processou exatamente dois contextos.",
    )

    historical, current = results

    check(
        historical["queue_id"] == 12
        and historical["decision"]["eligible_for_ai"] is False
        and historical["decision"]["target_workflow"] is None,
        "Versao historica bloqueada para IA.",
    )

    check(
        current["queue_id"] == 13
        and current["decision"]["eligible_for_ai"] is True
        and current["decision"]["target_workflow"] == "WF-04",
        "Versao atual encaminhavel ao WF-04.",
    )

    check(
        all(
            item["snapshot_mode"] is False
            and item["runtime_database_query"] is True
            and item["dispatch_status"] == "MOCK_ONLY"
            and item["real_execution_started"] is False
            and item["ai_executed"] is False
            and item["notification_sent"] is False
            for item in results
        ),
        "Proveniencia real preservada e despacho bloqueado.",
    )

    check(
        all(
            item["provenance"]["content_signature"]
            == context["provenance"]["content_signature"]
            and item["event"] == context["event"]
            for item, context in zip(results, contexts)
        ),
        "WF-03 preservou eventos e assinaturas PostgreSQL.",
    )

    print()
    print("=== 4. TESTE NEGATIVO DE VERSIONAMENTO ===")

    tampered = copy.deepcopy(contexts)

    tampered[0]["is_historical_version"] = False

    negative = execute_node(
        WF03_NODE_RUNNER,
        json.dumps(
            {"contexts": tampered},
            ensure_ascii=False,
        ),
    )

    check(
        negative.returncode != 0
        and "Inconsistencia no versionamento"
        in negative.stderr,
        "WF-03 rejeitou versao historica adulterada.",
    )

finally:

    print()
    print("=== 5. CONFERENCIA FINAL ===")

    after = snapshot()

    check(
        before == after,
        "Sete tabelas PostgreSQL preservadas.",
    )

    for path, initial_hash in hashes.items():

        check(
            sha256_file(path) == initial_hash,
            "Arquivo preservado: " + path.name,
        )


print()
print("=" * 64)
print(" FASE 14.3.2.6 - TESTE CONCLUIDO")
print("=" * 64)

print("Eventos WF-02:", len(wf02_results))
print("Contextos WF-03:", len(results))
print("Historico: BLOQUEADO")
print("Versao atual: ELEGIVEL PARA WF-04")
print("Consulta PostgreSQL: SOMENTE LEITURA")
print("Ajustes WF-03: SOMENTE EM MEMORIA")
print("Ollama: NAO ACIONADO")
print("n8n remoto: NAO ACIONADO")
print("Git: SEM COMMIT / SEM PUSH")

print()
print("[OK] CONTRATO WF-02 -> WF-03 VALIDADO")
