# SOC Intelligence Orchestrator
# Regressao integrada local - Etapa 12
#
# Uso:
# .\scripts\run-local-integrated-regression.ps1
#
# A FastAPI deve ser iniciada separadamente.
# Nenhuma credencial e escrita no repositorio.

param([switch]$IncludeRuntimeAI)



$root = Split-Path -Parent $PSScriptRoot

$python = Join-Path $root ".venv\Scripts\python.exe"

$secretFile = Join-Path $HOME `
    "soc-intelligence-local-secrets\bridge-http-token.dpapi"

$ptr = [IntPtr]::Zero
$secure = $null
$encrypted = $null
$token = $null
$tokenLoadedByRunner = $false

try {
    Write-Host "`n=== 1. VALIDAR LABORATORIO ===" -ForegroundColor Cyan

    Set-Location $root

    if (-not (Test-Path $python)) {
        throw "Python do ambiente virtual nao encontrado."
    }

    $branch = (git branch --show-current).Trim()

    if (
        $LASTEXITCODE -ne 0 -or
        $branch -notin @("feat/automated-integration-regression", "feat/runtime-database-local-consumer", "feat/runtime-ai-local-integration", "feat/runtime-ai-report-e2e-local", "main")
    ) {
        throw "Branch da Etapa 12 nao esta ativa."
    }

    if (-not (Test-Path $secretFile)) {
        throw "Token DPAPI nao encontrado."
    }

    # Nao substituir uma credencial previamente existente
    # no ambiente da sessao.
    if (Test-Path Env:\SOC_BRIDGE_HTTP_TOKEN) {
        throw "A variavel SOC_BRIDGE_HTTP_TOKEN ja existe nesta sessao."
    }

    $listener = @(
        Get-NetTCPConnection `
            -LocalAddress "127.0.0.1" `
            -LocalPort 8765 `
            -State Listen `
            -ErrorAction SilentlyContinue
    )

    if ($listener.Count -eq 0) {
        throw "Inicie primeiro a FastAPI em 127.0.0.1:8765."
    }

    Write-Host "[OK] API local detectada."

    Write-Host "`n=== 2. CARREGAR TOKEN DPAPI ===" -ForegroundColor Cyan

    $encrypted = Get-Content `
        -LiteralPath $secretFile `
        -Encoding ASCII `
        -TotalCount 1

    if ([string]::IsNullOrWhiteSpace($encrypted)) {
        throw "Arquivo DPAPI invalido."
    }

    $secure = ConvertTo-SecureString `
        -String $encrypted.Trim()

    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR(
        $secure
    )

    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR(
        $ptr
    )

    if ($token.Length -lt 32) {
        throw "Token LAB fora do contrato."
    }

    $env:SOC_BRIDGE_HTTP_TOKEN = $token
    $tokenLoadedByRunner = $true

    Write-Host "[OK] Credencial temporaria carregada."

    Write-Host "`n=== 3. EXECUTAR REGRESSAO INTEGRADA ===" `
        -ForegroundColor Cyan

    & $python -m unittest discover `
        -s tests `
        -p "local_integrated_regression.py" `
        -v

    if ($LASTEXITCODE -ne 0) {
        throw "Regressao integrada local reprovada."
    }

    Write-Host "`n=== 3B. REGRESSAO DINAMICA FASE 08 ===" `
        -ForegroundColor Cyan

    & $python -m unittest discover `
        -s tests `
        -p "local_runtime_regression.py" `
        -v

    if ($LASTEXITCODE -ne 0) {
        throw "Regressao dinamica Fase 08 reprovada."
    }

    Write-Host "[OK] Regressao dinamica aprovada."

    if ($IncludeRuntimeAI) {
        Write-Host "`n=== 3C. RUNTIME AI - OLLAMA REAL ===" -ForegroundColor Cyan

        & $python -m unittest discover -s tests -p "local_runtime_ai_regression.py" -v

        if ($LASTEXITCODE -ne 0) {
            throw "Homologacao Runtime AI reprovada."
        }

        Write-Host "[OK] Runtime AI local homologado." -ForegroundColor Green
    }

    Write-Host "`n[OK] REGRESSAO INTEGRADA APROVADA!" `
        -ForegroundColor Green
}
finally {
    Write-Host "`n=== 4. LIMPEZA OBRIGATORIA ===" `
        -ForegroundColor Cyan

    if ($tokenLoadedByRunner) {
        Remove-Item Env:\SOC_BRIDGE_HTTP_TOKEN `
            -ErrorAction SilentlyContinue
    }

    if ($ptr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
        $ptr = [IntPtr]::Zero
    }

    $token = $null
    $secure = $null
    $encrypted = $null

    Write-Host "[OK] Token temporario removido." `
        -ForegroundColor Green
}
