import copy
import hashlib
import json
import subprocess

from pathlib import Path

from src.reports.report_builder import validate_contract


ROOT = Path(__file__).resolve().parents[1]

WORKFLOW = ROOT / (
    "workflows/INTEGRACAO-WF01-WF02-WF03-WF04-LAB.json"
)

FIXTURE = ROOT / (
    "tests/fixtures/wf04_output_mock.json"
)


def check(condition, description):

    if not condition:
        raise AssertionError(description)

    print("[OK]", description, flush=True)


def digest(path):

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


NODE_RUNNER = r"""
const fs = require("node:fs");
const vm = require("node:vm");

const wf = JSON.parse(
  fs.readFileSync(
    "workflows/INTEGRACAO-WF01-WF02-WF03-WF04-LAB.json",
    "utf8"
  )
);

if (
  wf.active !== false ||
  wf.nodes.length !== 13 ||
  Object.keys(wf.connections).length !== 12
) {
  throw new Error("Estrutura LAB inesperada.");
}

const nodes = new Map(
  wf.nodes.map(node => [node.name, node])
);

if (nodes.size !== 13) {
  throw new Error("Nomes duplicados.");
}

const triggers = wf.nodes.filter(
  n => n.type === "n8n-nodes-base.manualTrigger"
);

if (triggers.length !== 1) {
  throw new Error("Manual Trigger invalido.");
}

const order = [];
let current = triggers[0].name;

while (current) {

  if (order.includes(current) || !nodes.has(current)) {
    throw new Error("Ciclo ou no desconhecido.");
  }

  order.push(current);

  const edge = wf.connections[current];

  if (!edge) {
    current = null;
    continue;
  }

  if (
    edge.main?.length !== 1 ||
    edge.main[0]?.length !== 1 ||
    edge.main[0][0].type !== "main" ||
    edge.main[0][0].index !== 0
  ) {
    throw new Error("Conexao inesperada.");
  }

  current = edge.main[0][0].node;
}

if (order.length !== 13) {
  throw new Error("Fluxo incompleto.");
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function execute(name, incoming) {

  const node = nodes.get(name);

  if (!node || node.type !== "n8n-nodes-base.code") {
    throw new Error("Code Node ausente: " + name);
  }

  const input = clone(incoming);

  const output = vm.runInNewContext(
    "(function(){\n" +
      node.parameters.jsCode +
    "\n})()",
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
    { timeout: 4000, filename: name }
  );

  if (!Array.isArray(output)) {
    throw new Error("Saida invalida: " + name);
  }

  return clone(output);
}

let items = [{ json: {} }];

for (const name of order.slice(1)) {
  items = execute(name, items);
}

process.stdout.write(
  JSON.stringify({
    executed_nodes: order.length,
    results: items.map(item => item.json)
  })
);
"""


def execute_wf04():

    result = subprocess.run(
        ["node", "-e", NODE_RUNNER],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=40,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Execucao JavaScript falhou:\n" +
            result.stderr
        )

    return json.loads(result.stdout)


def build_envelope(items, approved):

    if not isinstance(items, list) or len(items) != 2:
        raise ValueError(
            "Esperados exatamente dois resultados WF-04."
        )

    if (
        approved.get("schema_version") != "1.0"
        or approved.get("environment") != "LAB"
        or approved.get("origin") != "WF-04"
        or approved.get("fixture_type") != "MOCK_AI_RESPONSE"
        or approved.get("real_ollama_call") is not False
        or approved.get("ready_for_operational_dispatch") is not False
    ):
        raise ValueError("Fixture de referencia invalido.")

    ordered = sorted(
        copy.deepcopy(items),
        key=lambda r: r.get("queue_id", -1)
    )

    expected = approved.get("results")

    if not isinstance(expected, list) or len(expected) != 2:
        raise ValueError("Referencia WF-04 incompleta.")

    cleaned = []

    for actual, reference in zip(ordered, expected):

        if (
            actual.get("contract_validation") != "VALID"
            or actual.get("integration_mode") != "MOCK_SNAPSHOT"
            or actual.get("fixture_type") != "MOCK_AI_RESPONSE"
            or actual.get("real_ollama_call") is not False
            or actual.get("ready_for_operational_dispatch") is not False
            or actual.get("notification_sent") is not False
        ):
            raise ValueError(
                "Resultado WF-04 sem validacao autorizada."
            )

        binding = actual.get("context_binding", {})

        if (
            binding.get("status")
                != "MATCHED_TO_WF03_CONTEXT"
            or binding.get("method")
                != "STATIC_FIXTURE_COMPARISON"
            or binding.get("verified_against_database") is not False
            or binding.get("runtime_database_query") is not False
            or binding.get("operational_dispatch_allowed") is not False
        ):
            raise ValueError(
                "Vinculo WF-03/WF-04 invalido."
            )

        # Comparar todos os campos pertencentes ao resultado
        # original, nao somente queue_id e versionamento.

        for field, expected_value in reference.items():

            if (
                field not in actual
                or actual[field] != expected_value
            ):
                raise ValueError(
                    "Resultado WF-04 diverge da referencia: "
                    + field
                )

        eligible = reference["queue_id"] == 13

        decision = actual.get("decision", {})

        if (
            decision.get("eligible_for_report") is not eligible
            or decision.get("target_workflow")
                != ("WF-05" if eligible else None)
        ):
            raise ValueError(
                "Decisao de relatorio inconsistente."
            )

        # Os metadados exclusivos de transporte do n8n
        # nao substituem o contrato oficial Python.

        cleaned.append({
            field: copy.deepcopy(actual[field])
            for field in reference
        })

    envelope = {
        "schema_version": approved["schema_version"],
        "environment": approved["environment"],
        "origin": approved["origin"],
        "fixture_type": approved["fixture_type"],
        "real_ollama_call": False,
        "ready_for_operational_dispatch": False,
        "results": cleaned,
    }

    validate_contract(envelope)

    return envelope


print()
print("=" * 62)
print(" FASE 14.3.4.2 - ENVELOPE WF-04 / PYTHON")
print("=" * 62)

protected = [WORKFLOW, FIXTURE]

before = {
    path: digest(path)
    for path in protected
}

fixture = json.loads(
    FIXTURE.read_text(encoding="utf-8-sig")
)

try:

    print()
    print("=== 1. EXECUTAR WORKFLOW INTEGRADO ===")

    output = execute_wf04()

    check(
        output["executed_nodes"] == 13,
        "Treze nos percorridos.",
    )

    items = output["results"]

    check(
        len(items) == 2,
        "Dois resultados WF-04 recebidos.",
    )

    print()
    print("=== 2. CONSTRUIR ENVELOPE ===")

    envelope = build_envelope(items, fixture)

    historical, current = validate_contract(envelope)

    check(
        historical["queue_id"] == 12
        and historical["status"] == "SKIPPED",
        "Versao historica validada.",
    )

    check(
        current["queue_id"] == 13
        and current["status"] == "ANALYSIS_COMPLETED"
        and current["requires_human_review"] is True,
        "Versao atual validada para revisao.",
    )

    check(
        envelope["real_ollama_call"] is False
        and envelope[
            "ready_for_operational_dispatch"
        ] is False,
        "Contrato permanece em modo LAB/MOCK.",
    )

    print()
    print("=== 3. TESTES NEGATIVOS ===")

    cases = [
        ("tamper_queue", ("queue_id", 999)),
        (
            "tamper_signature",
            ("provenance", {
                **items[1]["provenance"],
                "content_signature": "f" * 64
            })
        ),
        (
            "tamper_analysis",
            ("analysis", {
                **items[1]["analysis"],
                "evidence_ids": ["LAB-EV-FAKE"]
            })
        ),
    ]

    for name, (field, value) in cases:

        tampered = copy.deepcopy(items)

        tampered[1][field] = value

        try:
            build_envelope(tampered, fixture)
        except ValueError:
            print("[OK] Bloqueado:", name)
        else:
            raise AssertionError(
                "Adulteracao aceita: " + name
            )

finally:

    print()
    print("=== 4. INTEGRIDADE DOS ARQUIVOS ===")

    for path in protected:

        check(
            digest(path) == before[path],
            "Preservado: " + path.name,
        )


print()
print("=" * 62)
print(" FASE 14.3.4.2 - TESTE APROVADO")
print("=" * 62)

print("Resultados recebidos:", len(items))
print("Resultados consolidados:", len(envelope["results"]))
print("validate_contract(): APROVADO")
print("Testes negativos:", len(cases))
print("Persistencia PostgreSQL: NAO EXECUTADA")
print("Ollama: NAO ACIONADO")
print("n8n remoto: NAO ACIONADO")
print("Git: SEM COMMIT / SEM PUSH")

print()
print("[OK] ENVELOPE WF-04 COMPATIVEL COM PYTHON")
