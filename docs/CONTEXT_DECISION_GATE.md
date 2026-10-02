# Context Decision Gate — SOC Intelligence Orchestrator

## Objetivo

Implementar uma camada deterministica de decisao antes
da futura analise de IA do laboratorio SOC-LAB.

Esta camada nao executa modelos de IA, nao escreve no
PostgreSQL e nao realiza despacho operacional.

## Arquitetura

```text
PostgreSQL LAB
      |
      v
FastAPI + HTTP Bearer
      |
      v
Local HTTP Context Client
      |
      v
Context Decision Gate
      |
      v
Decisao estruturada
```

## Modulos

- `src/context/decision_gate.py`
- `src/context/local_decision_pipeline.py`

## Regras de elegibilidade

O Decision Gate preserva a regra original do WF-03:

```python
eligible = queue_status == "PENDING" and not historical
```

Uma versao atual so pode prosseguir para revisao de IA
quando a fila estiver PENDING e os campos do contrato
forem consistentes.

## Decisoes

| Decisao | Condicao |
|---|---|
| READY_FOR_AI_REVIEW | Contexto atual e pendente |
| HISTORICAL_CONTEXT | Versao anterior preservada para rastreabilidade |
| BLOCKED_BY_POLICY | Restricao ou inconsistencia contratual |

A decisao READY_FOR_AI_REVIEW nao executa a IA.

## Homologacao HTTP real

As consultas foram realizadas por meio do consumidor
HTTP autenticado, da FastAPI e do PostgreSQL local.

| Queue | Versao | Decisao | Motivo |
|---|---:|---|---|
| 12 | 1 | HISTORICAL_CONTEXT | SUPERSEDED_VERSION |
| 13 | 2 | READY_FOR_AI_REVIEW | CURRENT_PENDING_CONTEXT |

Evento sintetico: LAB-0001.

Em ambos os cenarios:

- ai_execution_allowed: false;
- operational_dispatch_allowed: false;
- notification_sent: false;
- human_review_required: true.

## Testes

- Decision Gate: 11 testes.
- Local Decision Pipeline: 6 testes.
- Regressao conjunta com a ponte e consumidor: 43 testes esperados.

## Limites do escopo

O workflow E2E n8n permanece em MOCK_SNAPSHOT.

Nao ha conexao com a infraestrutura corporativa,
execucao automatica do Ollama ou notificacoes operacionais.

A API permanece restrita a localhost.
