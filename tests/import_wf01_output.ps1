$ErrorActionPreference = "Stop"

Set-Location "$HOME\soc-intelligence-orchestrator"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " IMPORTACAO DO OUTPUT REAL DO WF-01"
Write-Host "========================================" -ForegroundColor Cyan

Write-Host ""
Write-Host "Agora faca o seguinte:" -ForegroundColor Yellow
Write-Host "1. Volte ao n8n."
Write-Host "2. Abra o ultimo no do WF-01."
Write-Host "3. Entre em OUTPUT -> JSON."
Write-Host "4. Clique no icone de copiar o JSON completo."
Write-Host "5. Volte para este terminal."
Write-Host ""

Read-Host "Depois de copiar o JSON, pressione ENTER para continuar"

# ==========================================================
# LER E VALIDAR O CLIPBOARD
# ==========================================================

$raw = Get-Clipboard -Raw

if ([string]::IsNullOrWhiteSpace($raw)) {
    throw "Clipboard vazio. Nenhum arquivo foi alterado."
}

$raw = $raw.Trim()

if (-not $raw.StartsWith("[")) {
    throw "O clipboard nao comeca com um array JSON. Nenhum arquivo foi alterado."
}

try {

    $dados = ConvertFrom-Json -InputObject $raw -ErrorAction Stop

} catch {

    throw "O clipboard nao contem JSON valido. Nenhum arquivo foi alterado."

}

$eventos = @($dados)

if ($eventos.Count -ne 3) {
    throw "Esperados 3 eventos. Encontrados: $($eventos.Count)"
}

$cenarios = @(
    "NEW_EVENT",
    "EXACT_REPEAT",
    "MATERIAL_UPDATE"
)

$idColeta = $eventos[0].collection_id

if ([string]::IsNullOrWhiteSpace($idColeta)) {
    throw "collection_id ausente."
}

for ($i = 0; $i -lt 3; $i++) {

    $evento = $eventos[$i]

    if ($evento.schema_version -ne "1.0") {
        throw "Item $($i+1): versao de contrato invalida."
    }

    if ($evento.environment -ne "LAB") {
        throw "Item $($i+1): ambiente invalido."
    }

    if ($evento.collector -ne "WF-01") {
        throw "Item $($i+1): coletor incorreto."
    }

    if ($evento.target_workflow -ne "WF-02") {
        throw "Item $($i+1): destino incorreto."
    }

    if ($evento.validation.status -ne "VALID") {
        throw "Item $($i+1): validacao ausente."
    }

    if ($evento.collection_id -ne $idColeta) {
        throw "Os tres eventos nao pertencem a mesma coleta."
    }

    if ($evento.collection_sequence -ne ($i + 1)) {
        throw "Item $($i+1): sequencia incorreta."
    }

    if ($evento.raw_event.sample_case -ne $cenarios[$i]) {
        throw "Item $($i+1): cenario incorreto."
    }

    if ($evento.dispatch_status -ne "MOCK_ONLY") {
        throw "Item $($i+1): modo de despacho incorreto."
    }

    if ($evento.real_execution_started -ne $false) {
        throw "Item $($i+1): execucao real inesperada."
    }

}

Write-Host ""
Write-Host "[OK] Os tres registros foram validados." -ForegroundColor Green

# ==========================================================
# PRESERVAR O ARQUIVO ANTERIOR E GRAVAR O CORRETO
# ==========================================================

$destino = Join-Path (Get-Location) `
    "tests\fixtures\wf01_real_output.json"

if (Test-Path $destino) {

    $backup = "$destino.backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"

    Copy-Item -LiteralPath $destino -Destination $backup -ErrorAction Stop

    Write-Host "[OK] Backup do arquivo anterior criado." -ForegroundColor Green
}

$utf8 = New-Object System.Text.UTF8Encoding($false)

[System.IO.File]::WriteAllText(
    $destino,
    $raw,
    $utf8
)

# ==========================================================
# VALIDACAO FINAL PELO PYTHON
# ==========================================================

& ".\.venv\Scripts\python.exe" -m json.tool $destino |
    Out-Null

if ($LASTEXITCODE -ne 0) {
    throw "Falha na validacao final pelo Python."
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " OUTPUT REAL IMPORTADO COM SUCESSO"
Write-Host "========================================" -ForegroundColor Green
Write-Host "Eventos: $($eventos.Count)"
Write-Host "Collection ID: $idColeta"
Write-Host "JSON: VALIDO"
Write-Host "Arquivo: $destino"
Write-Host ""

code --reuse-window $destino