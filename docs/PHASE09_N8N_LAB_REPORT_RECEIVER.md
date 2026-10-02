# Fase 09 — Receptor Runtime AI Report (n8n LAB)

## Escopo e evidências da homologação local (02/10/2026)

A integração Python -> n8n Docker LAB recebeu o arquivo HTML sintético produzido anteriormente com Ollama local, sem nova execução do modelo. Webhook local `POST /webhook/soc-lab-runtime-report`, serviço Docker acessível pelo Windows somente em `127.0.0.1:5679`. A FastAPI Python permanece restrita a `127.0.0.1:8765`; o n8n não chama diretamente esse endpoint neste percurso.

| Cenário | Resultado verificado |
| --- | --- |
| Sonda de transporte **sem Header Auth** (workflow auxiliar anterior) | HTTP **403** |
| Sonda de transporte **com Header Auth** (workflow auxiliar anterior) | HTTP **200**, `ACCEPTED_LAB_PROBE` |
| Envio autenticado do HTML legítimo para este receptor | HTTP **200**, `ACCEPTED_RUNTIME_REPORT`, `HASH_VERIFIED_IN_N8N` |
| Envio autenticado do HTML alterado, com hash original mantido | HTTP **422**, `REJECTED_RUNTIME_REPORT`, `reason_code=HASH_MISMATCH`, `integrity_status=REJECTED` |

Nos testes do receptor, o nó Crypto recalculou SHA-256 (HEX) sobre a string `body.html` e o validador comparou com `body.html_sha256`. A primeira tentativa de adulteração foi detectada pelo Code Node, mas uma resposta HTTP 200 não controlada mostrou a necessidade de uma rejeição explícita. A versão exportada agora retorna recibo de rejeição e HTTP 422 por expressão no Respond to Webhook. A evidência acima corresponde ao reteste final HTTP 422 com JSON lido via `HttpClient` no PowerShell.

## Fluxo exportado

`01 - Receber Evento LAB` (POST, Header Auth) -> `01B - Calcular SHA256 do HTML` (Crypto Hash SHA256, `HEX`, valor `{{ $json.body.html }}`, saída `html_sha256_computed`) -> `02 - Validar Runtime AI Report` (contrato, marcadores HTML, SHA-256) -> `03 - Responder Confirmacao` (First Incoming Item, resposta HTTP por expressão `200` para aceito, `422` para rejeitado).

O arquivo `workflows/SOC-LAB-Runtime-AI-Report-Receiver.SANITIZED.json` mantém o estado `active=false`; foram removidos vínculos internos de credencial (`credentials` contendo ID/nome), ID de workflow, version ID e metadados da instância. **Ao importar a cópia em outro n8n**, configure manualmente a credencial `httpHeaderAuth` do primeiro nó, com nome de cabeçalho `X-SOC-LAB-KEY`. Nunca versione o *Value* da credencial, tokens ou arquivos DPAPI. O fluxo deverá permanecer não publicado fora de janelas controladas de teste.

## Contrato de laboratório

Entrada com `schema_version=1.0`, `environment=LAB`, `processor=LOCAL_RUNTIME_AI_REPORT`, `source_event_id=LAB-0001`, `historical_queue_id=12` e `historical_status=SKIPPED`, `current_queue_id=13`, `execution_mode=LOCAL_OLLAMA`, `report_status=AWAITING_HUMAN_REVIEW`, `test_only=true`, campos humanos/operacionais seguros, `html` e `html_sha256` hexadecimal com 64 caracteres. Os IDs fixos vinculam este artefato aos dados **sintéticos desta fixture**, não são um receptor genérico de produção.

Saída aceita: `transport_status=ACCEPTED_RUNTIME_REPORT`, `integrity_status=HASH_VERIFIED_IN_N8N`, `html_sha256_verified=true`, revisão humana obrigatória e despacho/notificações bloqueados. Saída recusada: `transport_status=REJECTED_RUNTIME_REPORT`, `integrity_status=REJECTED`, `html_sha256_verified=false`, `reason_code` (por exemplo, `HASH_MISMATCH`) e HTTP 422. O comprovante não ecoa HTML nem credenciais.

**Limite de segurança:** SHA-256 confere a correspondência do HTML recebido com o valor declarado no mesmo envio. Não demonstra autoria criptográfica isoladamente, não verifica novamente o conteúdo persistido no PostgreSQL e não aprova a análise. Header Auth controla a admissão. Dados sintéticos podem continuar presentes no histórico local de execuções do n8n, conforme as configurações de retenção.

## Estado e pendências

- [x] Python/Ollama/HTML homologados localmente, antes deste transporte
- [x] E2E MOCK de 20 nós homologado separadamente no n8n LAB
- [x] Transporte HTTP e Header Auth com evidências 403/200 no workflow de sonda
- [x] Receptor autenticado recebe HTML real de LAB
- [x] SHA-256 recalculado no Crypto e resultado legítimo aceito (200)
- [x] Adulteração controlada rejeitada com recibo JSON (422 / `HASH_MISMATCH`)
- [x] Receptor exportado sanitizado, sem vínculo de credencial no JSON público
- [ ] Orquestração inversa: n8n iniciando Python por canal de transporte autorizado
- [ ] E2E dinâmico corporativo com HTTPS, credenciais e autorização de infraestrutura
- [ ] Persistência/auditoria de recibos, política de retenção e revisão humana efetiva (fora deste teste)

Histórico anterior do projeto: commit da Fase 09 `de604a3`, CI remoto 23 suítes e 210/210 testes (run `37047930021`), consolidação documental `638ea64`. Esses testes CI são offline; os HTTP 403/200/422 acima são evidências locais manuais, não parte dos 210 testes do GitHub Actions.
