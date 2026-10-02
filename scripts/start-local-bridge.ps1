# SOC Intelligence Orchestrator
# Local PostgreSQL Bridge - LAB
#
# Somente localhost.
# Nenhuma porta publica.
# Nenhum despacho operacional.

$ErrorActionPreference = "Stop"

& {
    $root = Split-Path -Parent $PSScriptRoot

    Set-Location $root

    $python = Join-Path $root ".venv\Scripts\python.exe"

    $secretDir = Join-Path $HOME `
        "soc-intelligence-local-secrets"

    $dbSecret = Join-Path $secretDir `
        "bridge-password.dpapi"

    $httpSecret = Join-Path $secretDir `
        "bridge-http-token.dpapi"

    # Funcao auxiliar: recuperar uma credencial DPAPI.
    function Read-LabSecret {

        param(
            [Parameter(Mandatory)]
            [string]$File
        )

        $ptr = [IntPtr]::Zero
        $secure = $null
        $encrypted = $null

        try {
            $encrypted = Get-Content `
                -LiteralPath $File `
                -Encoding ASCII `
                -TotalCount 1 `
                -ErrorAction Stop

            if ([string]::IsNullOrWhiteSpace($encrypted)) {
                throw "Credencial vazia."
            }

            $secure = ConvertTo-SecureString `
                -String $encrypted.Trim() `
                -ErrorAction Stop

            $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR(
                $secure
            )

            return [Runtime.InteropServices.Marshal]::PtrToStringBSTR(
                $ptr
            )
        }
        finally {
            if ($ptr -ne [IntPtr]::Zero) {
                [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
            }

            $secure = $null
            $encrypted = $null
        }
    }

    try {

        Write-Host "`n=== SOC LOCAL BRIDGE ===" -ForegroundColor Cyan

        # Confirmar ambiente local.
        if (-not (Test-Path $python)) {
            throw "Python do ambiente virtual nao encontrado."
        }

        if (-not (Test-Path "src\bridge\app.py")) {
            throw "Modulo FastAPI nao encontrado."
        }

        foreach ($file in @($dbSecret, $httpSecret)) {
            if (-not (Test-Path $file)) {
                throw "Uma credencial DPAPI obrigatoria nao foi encontrada."
            }
        }

        # Nao iniciar uma segunda instancia na mesma porta.
        $listener = Get-NetTCPConnection `
            -LocalPort 8765 `
            -State Listen `
            -ErrorAction SilentlyContinue

        if ($listener) {
            throw "A porta 8765 ja esta em uso."
        }

        Write-Host "[OK] Estrutura validada." -ForegroundColor Green

        Write-Host "`n=== CREDENCIAIS ===" -ForegroundColor Cyan

        $env:SOC_BRIDGE_DB_PASSWORD = Read-LabSecret $dbSecret
        $env:SOC_BRIDGE_HTTP_TOKEN = Read-LabSecret $httpSecret

        if (
            [string]::IsNullOrWhiteSpace(
                $env:SOC_BRIDGE_DB_PASSWORD
            ) -or
            $env:SOC_BRIDGE_HTTP_TOKEN.Length -lt 32
        ) {
            throw "Credenciais nao passaram pela validacao."
        }

        Write-Host "[OK] Credenciais protegidas carregadas." `
            -ForegroundColor Green

        Write-Host "`n=== INICIANDO SERVICO ===" -ForegroundColor Cyan

        Write-Host "Ambiente: LAB"
        Write-Host "Interface: 127.0.0.1"
        Write-Host "Porta: 8765"
        Write-Host "Concorrencia maxima: 10"
        Write-Host "Keep-alive: 5 segundos"

        Write-Host "`nHealth: http://127.0.0.1:8765/health" `
            -ForegroundColor Yellow

        Write-Host "`nPressione Ctrl+C para encerrar." `
            -ForegroundColor Yellow

        # Foreground: permanece neste terminal ate ser interrompido.
        # As credenciais sao herdadas pelo processo Python,
        # sem aparecer como argumentos da linha de comando.

        & $python -m uvicorn `
            src.bridge.app:app `
            --host 127.0.0.1 `
            --port 8765 `
            --workers 1 `
            --limit-concurrency 10 `
            --timeout-keep-alive 5 `
            --no-access-log `
            --no-server-header

    }
    finally {

        Write-Host "`n=== LIMPEZA ===" -ForegroundColor Cyan

        Remove-Item Env:\SOC_BRIDGE_DB_PASSWORD `
            -ErrorAction SilentlyContinue

        Remove-Item Env:\SOC_BRIDGE_HTTP_TOKEN `
            -ErrorAction SilentlyContinue

        Write-Host "[OK] Credenciais temporarias removidas." `
            -ForegroundColor Green
    }
}