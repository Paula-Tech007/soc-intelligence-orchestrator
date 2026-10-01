"""
FASE 14.3.2.9

Homologacao local do workflow integrado WF-01/WF-02/WF-03.

- Node.js executa os Code Nodes extraidos do JSON.
- Respeita as conexoes sequenciais do workflow.
- Nao conecta ao PostgreSQL.
- Nao altera workflows originais.
"""

import hashlib
import json
import subprocess

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

WORKFLOW = ROOT / (
    "workflows/INTEGRACAO-WF01-WF02-WF03-LAB.json"
)

PROTECTED = [
    WORKFLOW,
    ROOT / "workflows/INTEGRACAO-WF01-WF02-LAB.json",
    ROOT / "workflows/WF-01-Coleta-de-Eventos.json",
    ROOT / "workflows/WF-02-Normalizacao-e-Deduplicacao.json",
    ROOT / "workflows/WF-03-Contexto-e-Correlacao.json",
    ROOT / "tests/fixtures/wf02_wf03_verified_export_lab.json",
]


def check(condition, message):
    if not condition:
        raise AssertionError(message)

    print("[OK]", message, flush=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


NODE_RUNNER = r"""
const fs = require("node:fs");
const vm = require("node:vm");

const mode = process.argv[1] || "normal";

const wf = JSON.parse(
  fs.readFileSync(
    "workflows/INTEGRACAO-WF01-WF02-WF03-LAB.json",
    "utf8"
  )
);

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function canonicalize(value) {

  if (Array.isArray(value)) {
    return value.map(canonicalize);
  }

  if (value && typeof value === "object") {

    return Object.fromEntries(
      Object.keys(value).sort().map(
        key => [key, canonicalize(value[key])]
      )
    );
  }

  return value;
}

const nodes = wf.nodes;

if (
  wf.active !== false ||
  nodes.length !== 10 ||
  Object.keys(wf.connections).length !== 9
) {
  throw new Error("Estrutura integrada inesperada.");
}

const names = nodes.map(node => node.name);

if (new Set(names).size !== 10) {
  throw new Error("Nomes de nos duplicados.");
}

const manual = nodes.filter(
  node => node.type === "n8n-nodes-base.manualTrigger"
);

if (manual.length !== 1) {
  throw new Error("Manual Trigger inesperado.");
}

// Reconstruir a ordem diretamente das conexoes,
// sem depender da posicao visual dos nos.

const order = [];

let current = manual[0].name;

while (current) {

  if (order.includes(current)) {
    throw new Error("Ciclo encontrado.");
  }

  order.push(current);

  const connection = wf.connections[current];

  if (!connection) {
    current = null;
    continue;
  }

  const outputs = connection.main;

  if (
    !Array.isArray(outputs) ||
    outputs.length !== 1 ||
    !Array.isArray(outputs[0]) ||
    outputs[0].length !== 1
  ) {
    throw new Error("Conexao nao sequencial.");
  }

  current = outputs[0][0].node;

  if (!names.includes(current)) {
    throw new Error("Destino nao encontrado.");
  }
}

if (order.length !== 10) {
  throw new Error("Nem todos os nos estao conectados.");
}

function execute(name, incoming) {

  const found = nodes.filter(node => node.name === name);

  if (found.length !== 1) {
    throw new Error("No nao identificado: " + name);
  }

  const node = found[0];

  if (node.type !== "n8n-nodes-base.code") {
    throw new Error("Tipo de no nao suportado: " + name);
  }

  const code = node.parameters.jsCode;

  const input = clone(incoming);

  const result = vm.runInNewContext(
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

  if (!Array.isArray(result)) {
    throw new Error("Saida invalida: " + name);
  }

  return clone(result);
}

let items = [{ json: {} }];

for (const name of order.slice(1)) {

  // Adulteracoes controladas entre os nos.
  // Nenhuma delas modifica os arquivos JSON.

  if (
    name ===
      "05 - Validar Exportacao e Preparar Contextos WF-03"
  ) {

    if (mode === "tamper_content") {

      items[2].json.normalized_event.severity = "critical";

    } else if (mode === "tamper_signed_content") {

      items[2].json.normalized_event.severity = "critical";

      // Simular inclusive uma nova assinatura canonica
      // para comprovar a comparacao com a exportacao.
      items[2].json.content_signature = JSON.stringify(
        canonicalize(items[2].json.normalized_event)
      );
    }
  }

  if (
    name === "02 - Validar Contexto e Versao" &&
    mode === "tamper_history"
  ) {

    items[0].json.is_historical_version = false;
  }

  items = execute(name, items);
}

if (mode !== "normal") {
  throw new Error("Adulteracao nao foi bloqueada: " + mode);
}

process.stdout.write(
  JSON.stringify({
    execution_order: order,
    results: items.map(item => item.json)
  })
);
"""


def run_node(mode):

    return subprocess.run(
        ["node", "-e", NODE_RUNNER, mode],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=40,
        check=False,
    )


print()
print("=" * 64)
print(" FASE 14.3.2.9 - HOMOLOGACAO LOCAL WF-01/WF-02/WF-03")
print("=" * 64)

for path in PROTECTED:
    if not path.is_file():
        raise FileNotFoundError(str(path))

before_hashes = {
    path: digest(path)
    for path in PROTECTED
}

try:

    print()
    print("=== 1. EXECUCAO POSITIVA ===")

    execution = run_node("normal")

    if execution.returncode != 0:
        raise RuntimeError(
            "Falha nos Code Nodes:\n"
            + execution.stderr
        )

    output = json.loads(execution.stdout)

    order = output["execution_order"]
    results = output["results"]

    check(
        len(order) == 10,
        "Dez nos percorridos pelas conexoes reais.",
    )

    check(
        len(results) == 2,
        "Somente dois contextos chegaram ao final do WF-03.",
    )

    historical, current = results

    print()
    print("=== 2. VALIDAR AS VERSOES ===")

    check(
        historical["queue_id"] == 12
        and historical["requested_version"] == 1
        and historical["current_version"] == 2
        and historical["is_historical_version"] is True
        and historical["decision"]["eligible_for_ai"] is False
        and historical["decision"]["target_workflow"] is None,
        "Queue 12: versao historica bloqueada.",
    )

    check(
        current["queue_id"] == 13
        and current["requested_version"] == 2
        and current["current_version"] == 2
        and current["is_historical_version"] is False
        and current["decision"]["eligible_for_ai"] is True
        and current["decision"]["target_workflow"] == "WF-04",
        "Queue 13: versao atual elegivel para WF-04.",
    )

    check(
        historical["investigation_id"]
        == current["investigation_id"],
        "Ambas as versoes pertencem a mesma investigacao.",
    )

    check(
        all(
            item["validation_status"] == "VALID"
            and item["snapshot_mode"] is True
            and item["runtime_database_query"] is False
            and item["dispatch_status"] == "MOCK_ONLY"
            and item["real_execution_started"] is False
            and item["ai_executed"] is False
            and item["notification_sent"] is False
            for item in results
        ),
        "Contratos mantiveram origem estatica e modo LAB/MOCK.",
    )

    check(
        historical["evidence_count"] == 1
        and current["evidence_count"] == 2,
        "Quantidade de evidencias preservada por versao.",
    )

    check(
        historical["provenance"]["content_signature"]
        != current["provenance"]["content_signature"],
        "Versoes apresentam assinaturas distintas.",
    )

    print()
    print("=== 3. TESTES NEGATIVOS ===")

    negative_cases = {
        "tamper_content":
            "Representacao canonica WF-02 divergente",

        "tamper_signed_content":
            "Evento WF-02 diverge da exportacao validada",

        "tamper_history":
            "Inconsistencia no versionamento",
    }

    for mode, expected_message in negative_cases.items():

        negative = run_node(mode)

        check(
            negative.returncode != 0
            and expected_message in negative.stderr,
            "Adulteracao bloqueada: " + mode,
        )

finally:

    print()
    print("=== 4. CONFERIR ARQUIVOS ===")

    for path, old_digest in before_hashes.items():

        check(
            digest(path) == old_digest,
            "Preservado: " + path.name,
        )


print()
print("=" * 64)
print(" FASE 14.3.2.9 - TESTE FUNCIONAL APROVADO")
print("=" * 64)

print("Nos executados: 10 (1 trigger simulado + 9 Code Nodes)")
print("Contextos finais:", len(results))
print("Testes negativos:", len(negative_cases))
print("Queue historica: 12")
print("Queue atual: 13")
print("Transporte: STATIC_VERIFIED_LAB_EXPORT")
print("Consulta PostgreSQL runtime: NAO")
print("Ollama: NAO ACIONADO")
print("n8n remoto: NAO ACIONADO")
print("Git: SEM COMMIT / SEM PUSH")

print()
print("[OK] WF-01 -> WF-02 -> WF-03 VALIDADO LOCALMENTE")
