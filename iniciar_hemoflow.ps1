# Inicia o HemoFlow (MySQL) a partir DESTA pasta.
# Uso:  .\iniciar_hemoflow.ps1            (porta 8000)
#       .\iniciar_hemoflow.ps1 -Porta 8001
# A senha do MySQL e pedida sem aparecer na tela e nao e gravada em arquivo.
# Se a senha estiver errada, ela e pedida de novo (ate 5 tentativas).
param([int]$Porta = 8000)

Set-Location -LiteralPath $PSScriptRoot
$teste = "import sys, app_mysql`ntry:`n    app_mysql.connect_db().close()`nexcept Exception as e:`n    print('  Erro:', e); sys.exit(1)"

for ($tentativa = 1; $tentativa -le 5; $tentativa++) {
    if (-not $env:HEMOFLOW_DB_PASSWORD) {
        Write-Host ""
        Write-Host "(Tentativa $tentativa de 5. Digite a senha e aperte Enter. Aparecem asteriscos; isso e normal.)"
        $sec = Read-Host "Senha do MySQL (usuario hemoflow_app)" -AsSecureString
        $env:HEMOFLOW_DB_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
        if (-not $env:HEMOFLOW_DB_PASSWORD) { Write-Host "A senha chegou vazia."; continue }
    }
    Write-Host "Conferindo a senha no MySQL..."
    python -c $teste
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Senha correta."
        $env:HEMOFLOW_PORT = "$Porta"
        python "$PSScriptRoot\app_mysql.py"
        exit $LASTEXITCODE
    }
    Write-Host "Nao foi possivel conectar ao MySQL (veja o erro acima). Tente novamente."
    Remove-Item Env:\HEMOFLOW_DB_PASSWORD -ErrorAction SilentlyContinue
}
Write-Host "Nao foi possivel conectar apos 5 tentativas."
Write-Host "Se esqueceu a senha do hemoflow_app, ela pode ser redefinida pelo root no MySQL Workbench."
exit 1
