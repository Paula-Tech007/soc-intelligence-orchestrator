"""Phase 09 - Explicit HTML report for Runtime AI results."""

from src.ai_engine.runtime_integrity import (
    build_runtime_integrity,
    verify_runtime_integrity,
)
from src.reports.report_builder import esc, html_list


def build_runtime_ai_report(runtime, record=None):
    if record is None:
        record = build_runtime_integrity(runtime)

    verify_runtime_integrity(runtime, record)

    result = runtime["wf04_result"]
    analysis = result["analysis"]
    mode = record["execution_mode"]

    if mode == "LOCAL_OLLAMA":
        origin = "OLLAMA LOCAL - ANALISE REAL"
        notice = (
            "Resposta gerada pelo modelo local. "
            "Nao representa validacao operacional ou revisao humana concluida."
        )
    else:
        origin = "MODELO INJETADO - TESTE OFFLINE"
        notice = (
            "Resposta sintetica utilizada exclusivamente nos testes offline."
        )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WF-05 | Runtime AI LAB</title>
<style>
body {{ font: 15px/1.6 Arial,sans-serif; margin: 2rem auto;
        max-width: 920px; padding: 0 1rem; color: #243247; }}
header, section {{ padding: 1rem 0; border-bottom: 1px solid #ccd5df; }}
h1, h2 {{ color: #18385b; }}
small {{ color: #55657a; }}
</style>
</head>
<body>
<header>
<h1>SOC Intelligence Orchestrator</h1>
<p>WF-05 | {esc(origin)}</p>
<p><strong>Ambiente:</strong> LAB</p>
<p>{esc(notice)}</p>
</header>

<section>
<h2>Identificacao e proveniencia</h2>
<p><strong>Evento:</strong> {esc(result["source_event_id"])}</p>
<p><strong>Investigacao:</strong> {esc(result["investigation_id"])}</p>
<p><strong>Queue analisada:</strong> {esc(result["queue_id"])}</p>
<p><strong>Versao atual:</strong> {esc(result["investigation_version"])}</p>
<p><strong>Queue historica:</strong> {esc(runtime["historical_queue_id"])}
(SKIPPED)</p>
<p><strong>Modelo:</strong> {esc(result["model"])}</p>
<p><strong>Content SHA-256:</strong>
{esc(record["identity"]["content_signature"])}</p>
<p><strong>Analysis SHA-256:</strong>
{esc(record["analysis_signature"])}</p>
<p><strong>Result key:</strong> {esc(record["result_key"])}</p>
</section>

<section>
<h2>Resumo assistivo</h2>
<p>{esc(analysis["summary"])}</p>
<h2>Avaliacao</h2>
<p>{esc(analysis["assessment"])}</p>
<h2>Evidencias referenciadas</h2>
<ul>{html_list(analysis["evidence_ids"])}</ul>
<h2>Limitacoes</h2>
<ul>{html_list(analysis["limitations"])}</ul>
<h2>Sugestoes para revisao humana</h2>
<ul>{html_list(analysis["review_actions"])}</ul>
</section>

<footer>
<p><strong>REVISAO HUMANA OBRIGATORIA E PENDENTE.</strong></p>
<small>Integridade SHA-256 verificada somente em memoria.
Nenhuma persistencia analitica, notificacao ou despacho operacional.</small>
</footer>
</body>
</html>"""