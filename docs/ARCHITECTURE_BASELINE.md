# Architecture Baseline - SOC Intelligence Orchestrator

## Referencia

- Baseline funcional atual: main, commit de604a3.
- Referencia historica Etapa 19: f2feb8e.
- Ambiente: laboratorio defensivo com dados sinteticos.
- Objetivo: apoiar a triagem SOC N1, reduzindo retrabalho por meio de
  deduplicacao, contexto, analise assistiva e rastreabilidade.
- Revisao humana obrigatoria.
- Despacho operacional e notificacoes reais desabilitados.

## Tres percursos distintos

### A - Demonstracao E2E n8n

WF-00 -> WF-01 -> WF-02 -> WF-03 -> WF-04 MOCK -> WF-05.

- Workflow principal com 20 nos e 19 conexoes.
- Manual Trigger e Code nodes.
- Entrada sintetica e contexto previamente exportado.
- IA MOCK.
- Saida: relatorio HTML aguardando revisao humana.

A homologacao desse percurso nao comprova integracao dinamica
entre o n8n remoto, o PostgreSQL local e o Ollama.

### B - Pipeline Python local

PostgreSQL LAB -> FastAPI autenticada -> Cliente HTTP ->
Decision Gate -> Revisao MOCK -> Integridade -> Relatorio.

- Ponte HTTP restrita a localhost.
- PostgreSQL LAB com acesso de leitura no percurso contextual.
- Versao historica bloqueada.
- Versao vigente encaminhada para revisao MOCK.
- Cache e assinaturas verificados.
- Observabilidade sanitizada opcional.

A homologacao local e independente do workflow E2E remoto.

### C - Persistencia analitica

Integrity Record -> Persistencia PostgreSQL ->
Comprovante -> Handoff persistente -> Rechecagem -> WF-05.

- Contrato proprio de persistencia.
- Idempotencia e conflitos transacionais.
- Rechecagem do registro antes do relatorio persistente.
- Testes dependentes do banco ficam fora do CI offline.

Nao confundir VERIFIED_IN_MEMORY com verificacao PostgreSQL.

## Matriz de responsabilidades

| Componente | Responsabilidade |
|---|---|
| WF-00 | Controle da orquestracao |
| WF-01 | Coleta e validacao inicial |
| WF-02 | Normalizacao e deduplicacao de eventos |
| WF-03 | Contexto, correlacao e proveniencia |
| decision_gate.py | Elegibilidade da versao investigativa |
| engine.py | Motor assistivo de IA |
| review_adapter.py | Adaptacao de contexto para MOCK |
| review_orchestrator.py | Coordenacao da revisao MOCK |
| cache.py | Evitar reanalise equivalente |
| integrity.py | Identidade e assinaturas SHA-256 |
| integrity_bridge.py | Adaptar integridade WF-04/WF-05 |
| integrity_persistence.py | Persistencia transacional |
| persistent_bridge.py | Coordenar contrato persistente |
| persistent_handoff.py | Rechecagem do registro persistido |
| report_builder.py | Validacao e geracao principal de HTML |
| integrated_mock_adapter.py | Integracao MOCK com WF-05 |
| observability/collector.py | Telemetria sanitizada |
| observability/pipeline.py | Wrapper de observabilidade |
| persistence_traceability.py | Metadados validados em memoria |
| memory_trace_registry.py | Idempotencia temporaria em memoria |

## Regras para continuidade

1. Reutilizar as implementacoes existentes antes de criar modulos.
2. Separar validacao em memoria de persistencia duravel.
3. Preservar historicos e snapshots como evidencias, nao como runtime novo.
4. Nao interpretar teste isolado como homologacao do E2E remoto.
5. Documentar contratos antes de generalizar o fixture LAB-0001.
6. Manter revisao humana e despacho operacional bloqueado.
7. Nao expor a ponte HTTP local publicamente.

## Entrega Python integrada - Etapa 19

O modulo `src/context/local_mock_composer.py` reutiliza
os contratos existentes em uma chamada LAB/MOCK.

Processa a versao historica e a vigente, gera revisao
simulada, integridade SHA-256 em memoria, HTML WF-05
e registro temporario idempotente.

Demonstrador: `scripts/demo-local-mock.py`.
CI remoto: 19 suites, 186/186 testes, run 37032159353.

A demonstracao utiliza snapshots exportados e nao realiza
nova consulta PostgreSQL, chamada real ao Ollama,
persistencia ou despacho operacional.

## Pontos ainda nao integrados

- Integracao dinamica do n8n remoto com a camada Python local.
- Execucao do Ollama no percurso E2E do n8n.
- Contratos genericos LAB/MOCK concluidos na Etapa 18; adaptacao ao percurso dinamico ainda pendente.
- Homologacao consolidada de todos os percursos em um runtime unico.

Qualquer integracao externa depende de ambiente autorizado e
revisao especifica de seguranca.

## Fases 08 e 09 - Integracao Python LAB homologada

- PostgreSQL LAB -> FastAPI localhost autenticada.
- Decision Gate preserva historico e seleciona versao vigente.
- WF-04 executa Ollama local mediante habilitacao explicita.
- runtime_integrity.py verifica SHA-256 em memoria.
- local_runtime_ai_report.py compoe o HTML a partir da mesma chamada IA.
- Revisao humana obrigatoria; notificacoes e despacho bloqueados.
- CI remoto: 23 suites e 210/210 testes, run 37047930021.
- Regressao real executada apenas no LAB, fora do CI offline.
- Persistencia/verificacao analitica no banco nao homologada neste percurso.
- E2E dinamico n8n remoto permanece pendente de transporte autorizado.
- Nao expor a ponte 127.0.0.1:8765 publicamente.
