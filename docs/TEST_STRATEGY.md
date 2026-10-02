# Test Strategy - SOC Intelligence Orchestrator

## Baseline vigente

Commit funcional publicado: `1e0fb62`.
GitHub Actions: execucao `37041432173`, SUCCESS.
Python 3.12: **22 suites e 204/204 testes aprovados remotamente**.
Nova integracao local HTML: homologada; CI de 210 testes pendente.

Historico:
- Etapa 17: 14 suites, 138 testes.
- Etapa 18: 18 suites, 180 testes.
- Etapa 19: 19 suites, 186 testes.

## Inventario Python

- Arquivos test_*.py apos nova entrega: 45.
- Arquivos contemplados pelos padroes CI: 24.
- Arquivos fora dos padroes do CI: 21.
- Padroes de CI preparados: 23 (bridge contempla dois arquivos).
- Testes procedurais podem exigir execucao separada.

## Suites presentes no GitHub Actions

| Padrao |
|---|
| test_bridge_*.py |
| test_local_http_client.py |
| test_decision_gate.py |
| test_local_decision_pipeline.py |
| test_ai_review_adapter.py |
| test_ai_review_orchestrator.py |
| test_ai_review_integrity.py |
| test_integrated_mock_regression.py |
| test_observability_collector.py |
| test_observed_mock_pipeline.py |
| test_observability_integration.py |
| test_integrated_mock_report.py |
| test_memory_traceability.py |
| test_memory_trace_registry.py |
| test_generic_wf05_contract.py |
| test_generic_integrated_mock_report.py |
| test_generic_memory_traceability.py |
| test_generic_memory_trace_registry.py |
| test_local_mock_composer.py |
| test_local_runtime_ai.py |
| test_runtime_ai_artifacts.py |
| test_local_runtime_ai_report.py |
| test_local_runtime_composer.py |

## Etapa 18 - Contratos genericos LAB/MOCK

Quatro suites offline adicionais: 42 testes.

- WF-05 generico: 12.
- Adaptador integrado generico: 12.
- Rastreabilidade generica: 8.
- Registro temporario generico: 10.

Regressao local consolidada: 138 + 42 = 180
testes unittest aprovados.

O teste procedural legado do WF-05 foi executado
separadamente, com sete verificacoes aprovadas.

O novo percurso exige contexto e evidencias confiaveis,
integridade SHA-256 e revisao humana. Nao constitui
validacao contra PostgreSQL ou execucao real de Ollama.

## Etapa 19 - Executor Python LAB/MOCK

- Nova suite: test_local_mock_composer.py (6 testes).
- Total homologado: 19 suites e 186 testes unittest.
- Demonstrador: scripts/demo-local-mock.py.
- Saida: HTML WF-05 na pasta temporaria.
- Cache e registro temporario validados na repeticao.
- Contextos provenientes de fixture sintetica exportada.
- Sem nova consulta PostgreSQL ou chamada Ollama real.
- CI remoto aprovado: execucao 37032159353.

## Fase 08 - Runtime Database local

- Nova suite offline: test_local_runtime_composer.py (6 testes).
- Homologacao com FastAPI/PostgreSQL real: aprovada no LAB.
- Teste protegido: tests/local_runtime_regression.py.
- Runner: scripts/run-local-integrated-regression.ps1.
- CI homologado: 20 suites e 192/192 testes.
- CI remoto: SUCCESS, execucao 37037435586.

Inventario previsto apos publicacao:
- Arquivos Python test_*.py: 42.
- Arquivos cobertos pelos padroes do CI: 21.
- Arquivos test_*.py fora do CI: 21.
- Regressao local opcional fora do CI offline.

Esta homologacao comprova consulta dinamica do contexto.
A integridade da analise permanece em memoria e o WF-04
utiliza modelo MOCK, sem Ollama real.

## Fase 09 - Runtime AI local

- Nova suite: test_local_runtime_ai.py (6 testes offline).
- Nova suite: test_runtime_ai_artifacts.py (6 testes offline).
- CI remoto confirmado: 22 padroes, 204/204 testes.
- Proxima ampliacao: 23 padroes, 210 testes.
- Teste real opcional: local_runtime_ai_regression.py.
- Dependencias reais: PostgreSQL LAB, FastAPI e Ollama local.
- Runner: run-local-integrated-regression.ps1 -IncludeRuntimeAI.
- Homologacao real local: SUCCESS.
- CI remoto de 204 testes: aprovado (37041432173).
- Nova ampliacao para 210 testes: pendente.

A chamada real nao integra o CI offline. O SHA-256
foi calculado sobre a analise, sem verificacao persistente.
Integridade em memoria e HTML Runtime AI aprovados offline.
O HTML com resposta real foi homologado localmente
pelo runner DPAPI, sem segunda chamada ao Ollama.
O relatorio permanece sem revisao humana concluida,
persistencia analitica ou despacho operacional.

## Oito candidatos a testes offline adicionais

Estes arquivos exigem uma validacao controlada antes de entrar no CI:

- test_ai_cache.py
- test_ai_engine.py
- test_ai_integrity.py
- test_integrity_bridge.py
- test_report_builder.py
- test_wf04_wf05_handoff.py
- test_persistent_bridge.py
- test_persistent_report.py

Os seis primeiros utilizam verificacoes procedurais.
Os dois ultimos possuem oito metodos de teste cada
e usam simulacoes nas dependencias persistentes.

A classificacao como candidato nao afirma que uma nova
execucao foi realizada durante a Etapa 17.

## Teste com dependencia PostgreSQL confirmada

test_persistent_handoff.py

O setUpClass executa snapshot() por connect_db() e prepara
um contrato usando prepare_persisted_integrity_contract().

O arquivo espera registros preexistentes, inclusive IDs
1 e 9. Manter fora do CI offline e nao executar contra
um banco de estado desconhecido.

## Doze arquivos pendentes de classificacao complementar

- test_ai_engine_live.py
- test_context_builder.py
- test_integrity_first_insert_race.py
- test_integrity_injected_rollback.py
- test_integrity_persistence_live.py
- test_ollama_smoke.py
- test_persistence_smoke.py
- test_wf010203_integrated_lab.py
- test_wf01_integration.py
- test_wf02_wf03_bridge_live.py
- test_wf03_integrated_contract.py
- test_wf04_envelope_integration.py

Foram identificados indicadores como connect_db,
ChatOllama, subprocess ou variaveis de ambiente.
Eles nao comprovam, isoladamente, acesso real a servicos.

## Outras modalidades

O repositorio tambem possui testes JavaScript, fixtures,
scripts auxiliares e testes de integracao local.
Eles nao integram automaticamente o conjunto oficial
de 186 testes Python do CI vigente.

## Criterios para ampliar o CI

1. Confirmar que o teste funciona sem servicos externos.
2. Examinar execucao de nivel superior e fixtures.
3. Impedir uso de credenciais reais.
4. Confirmar que mocks cobrem as chamadas operacionais.
5. Preservar os 138 testes anteriores.
6. Evitar descobertas duplicadas de classes importadas.
7. Documentar a contagem exata de cada nova suite.

Nao executar todos os testes por descoberta generica.
Testes live devem ter homologacao local independente.

## Limites da verificacao atual

A Etapa 17 fez analise estatica e levantamento do
repositorio. Nao executou testes adicionais,
nao acessou PostgreSQL e nao acionou Ollama.
