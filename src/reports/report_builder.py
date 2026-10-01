"""
SOC Intelligence Orchestrator - WF-05.

Geracao de relatorio HTML a partir do contrato MOCK WF-04.

Somente dados sinteticos.
Sem consultas ao banco.
Sem envio de notificacoes.
Sem acoes de resposta automatizadas.
"""

import html
import re
from datetime import datetime


def esc(value):
    """Evita interpretar conteudo do evento como HTML."""
    return html.escape(str(value), quote=True)


def validate_contract(contract):

    if not isinstance(contract, dict):
        raise ValueError("Contrato deve ser objeto JSON.")

    expected = {
        "schema_version": "1.0",
        "environment": "LAB",
        "origin": "WF-04",
        "fixture_type": "MOCK_AI_RESPONSE",
        "real_ollama_call": False,
        "ready_for_operational_dispatch": False,
    }

    for field, value in expected.items():
        if contract.get(field) != value:
            raise ValueError(
                f"Contrato geral invalido: {field}"
            )

    results = contract.get("results")

    if not isinstance(results, list) or len(results) != 2:
        raise ValueError(
            "Esperados dois resultados no fixture LAB."
        )

    by_version = {}

    for result in results:

        if not isinstance(result, dict):
            raise ValueError("Resultado invalido.")

        version = result.get("investigation_version")

        if type(version) is not int:
            raise ValueError("Versao invalida.")

        if version in by_version:
            raise ValueError("Versao duplicada.")

        by_version[version] = result

        required = {
            "schema_version": "1.0",
            "environment": "LAB",
            "processor": "WF-04",
            "dispatch_status": "MOCK_ONLY",
            "real_execution_started": False,
            "notification_sent": False,
        }

        for field, value in required.items():
            if result.get(field) != value:
                raise ValueError(
                    f"Resultado invalido: {field}"
                )

        provenance = result.get("provenance")

        if not isinstance(provenance, dict):
            raise ValueError("Proveniencia ausente.")

        if provenance.get("version") != version:
            raise ValueError(
                "Versao da proveniencia divergente."
            )

        signature = provenance.get("content_signature")

        if not isinstance(signature, str) or not re.fullmatch(
            r"[a-f0-9]{64}", signature
        ):
            raise ValueError(
                "Assinatura de conteudo invalida."
            )

    if set(by_version) != {1, 2}:
        raise ValueError(
            "Fixture esperado: versoes 1 e 2."
        )

    historical = by_version[1]
    current = by_version[2]

    if (
        historical.get("queue_id") != 12
        or historical.get("status") != "SKIPPED"
        or historical.get("ai_executed") is not False
        or historical.get("analysis") is not None
        or historical.get("requires_human_review") is not False
    ):
        raise ValueError(
            "Versao historica nao foi bloqueada."
        )

    if (
        current.get("queue_id") != 13
        or current.get("status") != "ANALYSIS_COMPLETED"
        or current.get("ai_executed") is not True
        or current.get("requires_human_review") is not True
    ):
        raise ValueError(
            "Versao atual nao autorizada para relatorio."
        )

    for field in ("investigation_id", "source_event_id"):
        if (
            not current.get(field)
            or current.get(field) != historical.get(field)
        ):
            raise ValueError(
                f"Identidade da investigacao invalida: {field}"
            )

    if current["source_event_id"] != "LAB-0001":
        raise ValueError(
            "Fixture nao corresponde ao evento LAB-0001."
        )

    analysis = current.get("analysis")

    if not isinstance(analysis, dict):
        raise ValueError("Analise estruturada ausente.")

    for field in ("summary", "assessment"):

        value = analysis.get(field)

        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"Texto obrigatorio invalido: {field}"
            )

    for field in (
        "evidence_ids",
        "limitations",
        "review_actions",
    ):

        values = analysis.get(field)

        if (
            not isinstance(values, list)
            or not all(
                isinstance(value, str) and bool(value.strip())
                for value in values
            )
        ):
            raise ValueError(
                f"Lista de analise invalida: {field}"
            )

    if set(analysis["evidence_ids"]) != {
        "LAB-EV-001", "LAB-EV-002"
    }:
        raise ValueError(
            "Referencias de evidencias inesperadas."
        )

    if len(analysis["evidence_ids"]) != 2:
        raise ValueError(
            "Referencias de evidencias duplicadas."
        )

    return historical, current


def html_list(values):

    if not values:
        return "<li>Nenhum item informado.</li>"

    return "\n".join(
        f"<li>{esc(value)}</li>"
        for value in values
    )


def build_report(contract):

    historical, current = validate_contract(contract)

    analysis = current["analysis"]

    provenance = current["provenance"]

    # Horario local com informacao de fuso.
    generated_at = datetime.now().astimezone()

    report_date = generated_at.strftime("%d/%m/%Y")
    report_time = generated_at.strftime("%H:%M:%S")
    report_timezone = generated_at.strftime("UTC%z")


    # Todos os campos provenientes do contrato passam
    # pelo escape antes de entrar no documento HTML.

    report = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WF-05 | SOC Intelligence Orchestrator</title>

<style>
* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    padding: 32px 20px;
    background: #f2f5fa;
    color: #172c4e;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 14px;
    line-height: 1.6;
}}

main {{
    max-width: 1120px;
    margin: auto;
    background: #ffffff;
    border: 1px solid #e4eaf2;
    border-radius: 12px;
    padding: 32px;
    box-shadow: 0 6px 28px rgba(25, 48, 83, .05);
}}

.header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 24px;
    margin-bottom: 24px;
}}

h1 {{
    margin: 0;
    color: #112a50;
    font-size: 27px;
    line-height: 1.25;
}}

.subtitle {{
    margin: 5px 0 0;
    color: #61748f;
    font-size: 15px;
}}

.date {{
    padding: 12px 18px;
    background: #f3f6fa;
    border-radius: 8px;
    color: #526680;
    white-space: nowrap;
}}

.notice {{
    display: flex;
    gap: 18px;
    align-items: center;
    background: #edf4ff;
    border: 1px solid #c5dcff;
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 26px;
}}

.notice-icon {{
    display: flex;
    justify-content: center;
    align-items: center;
    flex-shrink: 0;
    width: 48px;
    height: 48px;
    border-radius: 8px;
    background: #dceafe;
    color: #1265c8;
    font-size: 25px;
}}

.notice strong {{
    color: #174a94;
}}

.notice p {{
    margin: 4px 0 0;
}}

h2 {{
    margin: 0 0 12px;
    font-size: 18px;
    font-weight: 700;
    color: #102a50;
}}

.section {{
    padding: 18px 0;
    border-bottom: 1px solid #e1e8f0;
}}

.section:first-of-type {{
    padding-top: 0;
}}

.section p {{
    margin: 0 0 0 28px;
    color: #40546f;
}}

.meta {{
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
}}

.meta-card {{
    min-width: 0;
    background: #f5f7fa;
    border: 1px solid #e9eef5;
    border-radius: 7px;
    padding: 14px 17px;
}}

.meta-label {{
    display: block;
    color: #708099;
    font-size: 12px;
    margin-bottom: 3px;
}}

.meta-value {{
    display: block;
    font-weight: 600;
    color: #18345e;
    overflow-wrap: anywhere;
}}

.meta-value.regular {{
    font-weight: 400;
}}

.content {{
    margin-left: 28px;
}}

.content p {{
    margin: 0;
}}

ul {{
    margin: 4px 0;
    padding-left: 20px;
    color: #40546f;
}}

.info {{
    background: #f5f8fc;
    border-radius: 7px;
    padding: 14px 18px;
}}

.note {{
    margin-top: 9px !important;
    margin-left: 0 !important;
    font-size: 12px;
    color: #6a7e97 !important;
}}

.bottom-grid {{
    display: grid;
    grid-template-columns: 1.2fr 0.8fr;
    gap: 16px;
    margin-top: 22px;
}}

.bottom-card {{
    min-width: 0;
    padding: 20px;
    background: #f4f8ff;
    border: 1px solid #dbe9fd;
    border-radius: 8px;
}}

.bottom-card.version {{
    background: #f1faf5;
    border-color: #d7eee0;
}}

.bottom-card h2 {{
    font-size: 16px;
}}

.trace {{
    display: grid;
    grid-template-columns: 155px minmax(0, 1fr);
    gap: 5px 12px;
    font-size: 12px;
}}

.trace strong {{
    color: #38516e;
}}

.trace span {{
    overflow-wrap: anywhere;
}}

.bottom-card p {{
    margin: 0;
    font-size: 13px;
    color: #40546f;
}}

footer {{
    display: flex;
    justify-content: space-between;
    gap: 16px;
    border-top: 1px solid #e1e8f0;
    padding-top: 18px;
    margin-top: 25px;
    font-size: 12px;
    color: #728199;
}}

@media (max-width: 760px) {{
    body {{
        padding: 10px;
    }}

    main {{
        padding: 20px;
    }}

    .header,
    footer {{
        flex-direction: column;
        align-items: flex-start;
    }}

    .date {{
        white-space: normal;
    }}

    .meta {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }}

    .bottom-grid {{
        grid-template-columns: 1fr;
    }}
}}

@media (max-width: 480px) {{
    .meta {{
        grid-template-columns: 1fr;
    }}

    .trace {{
        grid-template-columns: 1fr;
    }}
}}

@media print {{
    body {{
        background: white;
        padding: 0;
    }}

    main {{
        border: 0;
        box-shadow: none;
        max-width: none;
        padding: 8px;
    }}

    .meta-card,
    .bottom-card,
    .notice {{
        break-inside: avoid;
    }}
}}
</style>
</head>

<body>
<main>

<header class="header">
    <div>
        <h1>SOC Intelligence Orchestrator</h1>
        <p class="subtitle">
            WF-05 | Relatório de análise assistiva
        </p>
    </div>

    <div class="date">
        <strong>Gerado em:</strong><br>
        {report_date}<br>
        <strong>{report_time}</strong><br>
        <small>{report_timezone}</small>
        <hr style="border:0;border-top:1px solid #dce4ef;margin:8px 0;">
        <strong>Ambiente:</strong> LAB<br>
        <strong>Origem:</strong> WF-04 / MOCK
    </div>
</header>

<div class="notice">
    <div class="notice-icon" aria-hidden="true">&#9881;</div>

    <div>
        <strong>LABORATORIO - ANALISE SIMULADA</strong>
        <p>
            Este documento utiliza uma resposta simulada do WF-04.
            O n8n não executou uma chamada real ao Ollama.
            Nenhuma ação operacional foi realizada.
        </p>
    </div>
</div>

<section class="section">
    <h2>Identificação</h2>

    <div class="meta">

        <div class="meta-card">
            <span class="meta-label">Evento</span>
            <span class="meta-value">
                {esc(current["source_event_id"])}
            </span>
        </div>

        <div class="meta-card">
            <span class="meta-label">Queue ID</span>
            <span class="meta-value">
                {esc(current["queue_id"])}
            </span>
        </div>

        <div class="meta-card">
            <span class="meta-label">Versão analisada</span>
            <span class="meta-value">
                {esc(current["investigation_version"])}
            </span>
        </div>

        <div class="meta-card">
            <span class="meta-label">Investigação</span>
            <span class="meta-value regular">
                {esc(current["investigation_id"])}
            </span>
        </div>

        <div class="meta-card">
            <span class="meta-label">Status</span>
            <span class="meta-value">
                {esc(current["status"])}
            </span>
        </div>

        <div class="meta-card">
            <span class="meta-label">Modelo declarado</span>
            <span class="meta-value regular">
                {esc(current.get("model", "NAO INFORMADO"))}
                (resposta MOCK)
            </span>
        </div>

    </div>
</section>

<section class="section">
    <h2>Resumo da análise</h2>
    <div class="content">
        <p>{esc(analysis["summary"])}</p>
    </div>
</section>

<section class="section">
    <h2>Avaliação assistiva</h2>
    <div class="content">
        <p>{esc(analysis["assessment"])}</p>
    </div>
</section>

<section class="section">
    <h2>Referências das evidências</h2>

    <div class="content info">
        <ul>
            {html_list(analysis["evidence_ids"])}
        </ul>

        <p class="note">
            O contrato WF-04 fornece somente as referências
            das evidências. O conteúdo original deverá ser
            consultado durante a revisão humana.
        </p>
    </div>
</section>

<section class="section">
    <h2>Limitações da análise</h2>

    <div class="content">
        <ul>
            {html_list(analysis["limitations"])}
        </ul>
    </div>
</section>

<section class="section">
    <h2>Sugestões para revisão humana</h2>

    <div class="content">
        <ul>
            {html_list(analysis["review_actions"])}
        </ul>
    </div>
</section>

<div class="bottom-grid">

    <div class="bottom-card">
        <h2>Rastreabilidade</h2>

        <div class="trace">
            <strong>Base declarada:</strong>
            <span>{esc(provenance.get("database"))}</span>

            <strong>Tabela declarada:</strong>
            <span>{esc(provenance.get("table"))}</span>

            <strong>Versão:</strong>
            <span>{esc(provenance["version"])}</span>

            <strong>Assinatura:</strong>
            <span>{esc(provenance["content_signature"])}</span>
        </div>
    </div>

    <div class="bottom-card version">
        <h2>Controle de versões</h2>

        <p>
            A versão
            <strong>{esc(historical["investigation_version"])}</strong>
            (queue {esc(historical["queue_id"])})
            foi classificada como
            <strong>SKIPPED</strong>
            e não foi incluída na análise.
        </p>
    </div>

</div>

<footer>
    <span>SOC Intelligence Orchestrator | Ambiente LAB</span>

    <span>
        Revisão humana obrigatória.
        Documento sem finalidade operacional.
    </span>
</footer>

</main>
</body>
</html>
"""

    return report
