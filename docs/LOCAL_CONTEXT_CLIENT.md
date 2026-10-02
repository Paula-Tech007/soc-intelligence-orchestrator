# Local HTTP Context Client — SOC Intelligence Orchestrator

## Objetivo

Implementar um consumidor HTTP autenticado para recuperar
contextos investigativos reais da ponte FastAPI local.

Esta implementacao pertence exclusivamente ao laboratorio SOC-LAB.

## Arquitetura

```text
Cliente Python
    |
    v
HTTP Bearer - localhost
    |
    v
FastAPI - WF-03
    |
    v
PostgreSQL - soc_bridge_ro
    |
    v
Contrato JSON validado
```

## Implementacao

Arquivo: `src/context/local_http_client.py`

Funcao principal: `fetch_local_context(queue_id)`.

Controles:

- Consulta exclusiva ao endpoint local configurado no codigo.
- Bearer Token obtido de variavel de ambiente.
- Validacao de identificador e envelope HTTP.
- Bloqueio de redirecionamentos.
- Timeout de cinco segundos.
- Rejeicao de despacho operacional.
- Preservacao da identificacao de versoes historicas.
- Ausencia de operacoes de escrita e notificacoes.

## Testes automatizados

Arquivo: `tests/test_local_http_client.py`.

Resultado: 9 testes aprovados.

Os testes utilizam respostas HTTP simuladas e nao
exigem conexao real ao PostgreSQL.

## Homologacao real

A comunicacao HTTP foi validada com a FastAPI local
e o PostgreSQL do laboratorio.

| Queue | Versao | Historico | Elegivel para revisao |
|---|---:|---|---|
| 12 | 1 | True | False |
| 13 | 2 | False | True |

Evento sintetico: `LAB-0001`.

Em ambas as consultas, o despacho operacional permaneceu bloqueado.

## Limites do escopo

Esta entrega nao integra a API ao n8n corporativo.

O workflow E2E permanece em modo `MOCK_SNAPSHOT`.

Nenhuma API foi exposta publicamente e nenhuma notificacao
operacional foi executada.