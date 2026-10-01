const fs = require("node:fs");
const vm = require("node:vm");
const crypto = require("node:crypto");
const assert = require("node:assert/strict");

const protectedFiles = [
  "workflows/WF-01-Coleta-de-Eventos.json",
  "workflows/WF-02-Normalizacao-e-Deduplicacao.json",
  "workflows/WF-03-Contexto-e-Correlacao.json",
  "workflows/WF-04-Motor-de-IA.json",
  "workflows/INTEGRACAO-WF01-WF02-LAB.json",
  "workflows/INTEGRACAO-WF01-WF02-WF03-LAB.json",
  "workflows/INTEGRACAO-WF01-WF02-WF03-WF04-LAB.json",
  "tests/fixtures/wf02_wf03_verified_export_lab.json",
  "tests/fixtures/wf04_output_mock.json"
];

function hash(filename) {
  return crypto.createHash("sha256")
    .update(fs.readFileSync(filename))
    .digest("hex");
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function check(condition, message) {
  assert.ok(condition, message);
  console.log("[OK]", message);
}

console.log("");
console.log("========================================================");
console.log(" FASE 14.3.3.3 - HOMOLOGACAO WF-01 A WF-04");
console.log("========================================================");

const hashesBefore = new Map(
  protectedFiles.map(file => [file, hash(file)])
);

const wf = JSON.parse(fs.readFileSync(
  "workflows/INTEGRACAO-WF01-WF02-WF03-WF04-LAB.json",
  "utf8"
));

check(wf.active === false, "Workflow integrado inativo.");
check(wf.nodes.length === 13, "Treze nos encontrados.");

const nodes = new Map(
  wf.nodes.map(node => [node.name, node])
);

check(nodes.size === 13, "Nomes de nos unicos.");

const triggers = wf.nodes.filter(
  node => node.type === "n8n-nodes-base.manualTrigger"
);

check(triggers.length === 1, "Um Manual Trigger encontrado.");

// Reconstruir a sequencia pelas conexoes do JSON.
const order = [];
let current = triggers[0].name;

while (current) {
  assert.ok(!order.includes(current), "Ciclo detectado.");
  assert.ok(nodes.has(current), "No inexistente.");

  order.push(current);

  const edge = wf.connections[current];

  if (!edge) {
    current = null;
    break;
  }

  assert.equal(edge.main.length, 1);
  assert.equal(edge.main[0].length, 1);
  assert.equal(edge.main[0][0].type, "main");
  assert.equal(edge.main[0][0].index, 0);

  current = edge.main[0][0].node;
}

check(order.length === 13, "Treze nos conectados em sequencia.");
check(
  Object.keys(wf.connections).length === 12,
  "Doze conexoes encontradas."
);

const adapterName =
  "06 - Vincular Resultado MOCK ao Contexto WF-03";

function executeNode(name, incoming) {
  const node = nodes.get(name);

  assert.ok(node, `No ausente: ${name}`);
  assert.equal(node.type, "n8n-nodes-base.code");

  const code = node.parameters.jsCode;
  const input = clone(incoming);

  const output = vm.runInNewContext(
    "(function () {\n" + code + "\n})()",
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

  assert.ok(Array.isArray(output), `Saida invalida: ${name}`);

  return clone(output);
}

function executeWorkflow(mode = "normal") {
  let items = [{ json: {} }];

  for (const name of order.slice(1)) {

    // Alterar apenas copias dos dados em memoria.
    // Os arquivos e o fixture incorporado permanecem intactos.

    if (name === adapterName) {

      if (mode === "tamper_queue") {
        items[1].json.queue_id = 999;
      }

      if (mode === "tamper_provenance") {
        items[1].json.provenance.content_signature =
          "f".repeat(64);
      }

      if (mode === "tamper_evidence") {
        items[1].json.event.evidence.push({
          evidence_id: "LAB-EV-FAKE",
          type: "synthetic_test"
        });
      }

      if (mode === "tamper_history") {
        items[0].json.decision.eligible_for_ai = true;
        items[0].json.decision.target_workflow = "WF-04";
      }
    }

    items = executeNode(name, items);
  }

  return items.map(item => item.json);
}

console.log("");
console.log("=== 1. EXECUCAO POSITIVA ===");

const results = executeWorkflow();

check(
  results.length === 2,
  "Dois resultados WF-04 produzidos."
);

const historical = results.find(r => r.queue_id === 12);
const latest = results.find(r => r.queue_id === 13);

check(
  Boolean(historical && latest),
  "Queues 12 e 13 preservadas."
);

check(
  historical.investigation_version === 1 &&
  historical.status === "SKIPPED" &&
  historical.ai_executed === false &&
  historical.analysis === null &&
  historical.requires_human_review === false &&
  historical.decision.eligible_for_report === false,
  "Versao historica bloqueada para nova analise."
);

check(
  latest.investigation_version === 2 &&
  latest.status === "ANALYSIS_COMPLETED" &&
  latest.ai_executed === true &&
  latest.requires_human_review === true &&
  latest.contract_validation === "VALID" &&
  latest.decision.eligible_for_report === true &&
  latest.decision.target_workflow === "WF-05",
  "Versao atual MOCK validada para WF-05."
);

check(
  JSON.stringify(
    [...latest.analysis.evidence_ids].sort()
  ) === JSON.stringify(
    ["LAB-EV-001", "LAB-EV-002"]
  ),
  "Analise MOCK associada as duas evidencias esperadas."
);

check(
  historical.investigation_id === latest.investigation_id &&
  historical.provenance.version === 1 &&
  latest.provenance.version === 2,
  "Identidade e proveniencia versionada preservadas."
);

check(
  results.every(r =>
    r.fixture_type === "MOCK_AI_RESPONSE" &&
    r.real_ollama_call === false &&
    r.real_execution_started === false &&
    r.notification_sent === false &&
    r.ready_for_operational_dispatch === false &&
    r.dispatch_status === "MOCK_ONLY" &&
    r.context_binding.status === "MATCHED_TO_WF03_CONTEXT" &&
    r.context_binding.method === "STATIC_FIXTURE_COMPARISON" &&
    r.context_binding.runtime_database_query === false &&
    r.context_binding.verified_against_database === false &&
    r.context_binding.operational_dispatch_allowed === false
  ),
  "Vinculo estatico LAB/MOCK e despacho bloqueado."
);

console.log("");
console.log("=== 2. TESTES NEGATIVOS ===");

const negativeCases = [
  {
    mode: "tamper_queue",
    message: "Identidade ou proveniencia WF-03/WF-04 divergente."
  },
  {
    mode: "tamper_provenance",
    message: "Identidade ou proveniencia WF-03/WF-04 divergente."
  },
  {
    mode: "tamper_evidence",
    message: "Resultado MOCK atual nao corresponde ao contexto."
  },
  {
    mode: "tamper_history",
    message: "Versao historica nao pode solicitar analise."
  }
];

for (const test of negativeCases) {
  assert.throws(
    () => executeWorkflow(test.mode),
    error => error.message.includes(test.message),
    `Adulteracao nao bloqueada: ${test.mode}`
  );

  console.log("[OK] Bloqueado:", test.mode);
}

console.log("");
console.log("=== 3. INTEGRIDADE DOS ARQUIVOS ===");

for (const file of protectedFiles) {
  check(
    hash(file) === hashesBefore.get(file),
    "Preservado: " + file.split("/").pop()
  );
}

console.log("");
console.log("========================================================");
console.log(" FASE 14.3.3.3 - HOMOLOGACAO APROVADA");
console.log("========================================================");

console.log("Nos percorridos:", order.length);
console.log("Resultados WF-04:", results.length);
console.log("Testes negativos:", negativeCases.length);
console.log("Queue 12: SKIPPED");
console.log("Queue 13: ANALYSIS_COMPLETED (MOCK)");
console.log("Integracao: STATIC_FIXTURE_COMPARISON");
console.log("PostgreSQL runtime: NAO ACIONADO");
console.log("Ollama: NAO ACIONADO");
console.log("n8n remoto: NAO ACIONADO");
console.log("Git: SEM COMMIT / SEM PUSH");

console.log("");
console.log("[OK] WF-01 -> WF-04 VALIDADO LOCALMENTE");
