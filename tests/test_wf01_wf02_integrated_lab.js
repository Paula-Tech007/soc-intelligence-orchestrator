const fs = require("node:fs");
const crypto = require("node:crypto");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const path = require("node:path");

const files = [
  "workflows/WF-01-Coleta-de-Eventos.json",
  "workflows/WF-02-Normalizacao-e-Deduplicacao.json",
  "workflows/INTEGRACAO-WF01-WF02-LAB.json"
];

function sha256(filename) {
  return crypto.createHash("sha256")
    .update(fs.readFileSync(filename))
    .digest("hex");
}

const before = files.map(sha256);

const workflow = JSON.parse(
  fs.readFileSync(files[2], "utf8")
);

assert.equal(workflow.active, false);
assert.equal(workflow.nodes.length, 7);
assert.equal(Object.keys(workflow.connections).length, 6);

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function executeNode(name, items) {
  const matches = workflow.nodes.filter(n => n.name === name);
  assert.equal(matches.length, 1, `No nao encontrado: ${name}`);

  const code = matches[0].parameters.jsCode;
  assert.equal(typeof code, "string");

  const input = clone(items);

  const result = vm.runInNewContext(
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
    { timeout: 3000, filename: name }
  );

  assert.ok(Array.isArray(result), `Saida invalida: ${name}`);

  return clone(result);
}

function check(condition, message) {
  assert.ok(condition, message);
  console.log("[OK]", message);
}

console.log("");
console.log("====================================================");
console.log(" FASE 14.3.1.2 - TESTE FUNCIONAL LOCAL");
console.log("====================================================");

const collected = executeNode(
  "01 - Coletar Eventos Sinteticos",
  [{ json: {} }]
);

check(collected.length === 3, "WF-01 gerou tres eventos.");

const validated = executeNode(
  "02 - Validar Eventos",
  collected
);

check(
  validated.every(x => x.json.validation.status === "VALID"),
  "WF-01 validou os tres eventos."
);

const delivered = executeNode(
  "03 - Preparar Entrega ao WF-02",
  validated
);

check(
  delivered.every(x =>
    x.json.collection_status === "COLLECTED_VALIDATED"
  ),
  "WF-01 preparou a entrega ao WF-02."
);

const adapted = executeNode(
  "04 - Adaptar Contrato WF-01 para WF-02",
  delivered
);

check(
  adapted.every(x =>
    x.json.raw_event.source_event_id === x.json.source_event_id
  ),
  "Adaptador preservou a identidade dos eventos."
);

const deduplicated = executeNode(
  "02 - Normalizar e Deduplicar",
  adapted
);

const audited = executeNode(
  "03 - Validar Decisoes e Auditoria",
  deduplicated
);

const expected = [
  ["NEW_EVENT", true, 1, 1],
  ["EXACT_REPEAT", false, 1, 2],
  ["MATERIAL_UPDATE", true, 2, 3]
];

assert.equal(audited.length, 3);

console.log("");
console.log("=== RESULTADOS DA DEDUPLICACAO ===");

audited.forEach((item, i) => {
  const r = item.json;
  const [status, analyze, version, occurrences] = expected[i];

  assert.equal(r.deduplication.status, status);
  assert.equal(r.decision.should_analyze, analyze);
  assert.equal(r.deduplication.investigation_version, version);
  assert.equal(r.deduplication.occurrence_count, occurrences);
  assert.equal(r.audit.status, "VALIDATED");
  assert.equal(r.audit.notification_sent, false);
  assert.equal(r.audit.ai_executed, false);

  console.log(
    `[OK] Evento ${i + 1}: ${status}` +
    ` | analisar=${analyze}` +
    ` | versao=${version}` +
    ` | ocorrencias=${occurrences}`
  );
});

check(
  JSON.stringify(
    audited[0].json.normalized_event
  ) === JSON.stringify(
    audited[1].json.normalized_event
  ),
  "Repeticao possui conteudo normalizado identico."
);

check(
  audited[2].json.deduplication.new_evidence_ids.includes(
    "LAB-EV-002"
  ),
  "Atualizacao material identificou a nova evidencia."
);

console.log("");
console.log("=== TESTES NEGATIVOS ===");

// Evento com duas evidencias de mesmo identificador.
const tamperedCollection = clone(collected);

tamperedCollection[0].json.raw_event.evidence.push(
  clone(tamperedCollection[0].json.raw_event.evidence[0])
);

assert.throws(
  () => executeNode(
    "02 - Validar Eventos",
    tamperedCollection
  ),
  /Evidencias duplicadas/
);

console.log("[OK] Evidencia duplicada bloqueada.");

// Contrato de entrega sem validacao autorizada.
const tamperedDelivery = clone(delivered);

tamperedDelivery[0].json.validation.status = "INVALID";

assert.throws(
  () => executeNode(
    "04 - Adaptar Contrato WF-01 para WF-02",
    tamperedDelivery
  ),
  /Contrato WF-01 nao autorizado/
);

console.log("[OK] Contrato adulterado bloqueado.");

check(
  files.every((filename, index) =>
    sha256(filename) === before[index]
  ),
  "Tres arquivos JSON preservados."
);

console.log("");
console.log("====================================================");
console.log(" FASE 14.3.1.2 - TESTE FUNCIONAL APROVADO");
console.log("====================================================");
console.log("Cenarios positivos: 3/3");
console.log("Cenarios negativos: 2/2");
console.log("Workflow integrado: INATIVO");
console.log("PostgreSQL: NAO ACIONADO");
console.log("Ollama: NAO ACIONADO");
console.log("n8n remoto: NAO ACIONADO");
console.log("Git: SEM COMMIT / SEM PUSH");
console.log("");
console.log("[OK] WF-01 -> WF-02 VALIDADO LOCALMENTE");
