# Inicia o HemoFlow (MySQL) a partir DESTA pasta.
# Uso:  .\iniciar_hemoflow.ps1            (porta 8000)
#       .\iniciar_hemoflow.ps1 -Porta 8001
# A senha do MySQL e pedida sem aparecer na tela e nao e gravada em arquivo.
# Se a senha estiver errada, ela e pedida de novo (ate 5 tentativas).
param([int]$Porta = 8000)

Set-Location -LiteralPath $PSScriptRoot

# Gmail que envia o "Esqueceu sua senha?" (opcional). Usa uma SENHA DE APP do Google,
# nunca a senha normal da conta. Nada é gravado em arquivo: vale só enquanto o servidor estiver aberto.
function Configurar-Email {
    if ($env:HEMOFLOW_EMAIL_USER -and $env:HEMOFLOW_EMAIL_PASSWORD) { return }
    Write-Host ""
    Write-Host "Recuperacao de senha por e-mail (opcional)."
    $gmail = ""
    while (-not $gmail) {
        $gmail = (Read-Host "Gmail que envia os e-mails (ex.: nome@gmail.com; digite N para pular)").Trim()
        if ($gmail -in @("N", "n")) { Write-Host "Sem e-mail: o 'Esqueceu sua senha?' fica desativado nesta sessao."; return }
        if ($gmail -and $gmail -notmatch "^[^@\s]+@[^@\s]+\.[^@\s]+$") { Write-Host "Digite um e-mail completo, por exemplo nome@gmail.com."; $gmail = "" }
    }
    for ($i = 1; $i -le 3; $i++) {
        $sec = Read-Host "Senha de app do Gmail (16 letras; aparecem asteriscos)" -AsSecureString
        $env:HEMOFLOW_EMAIL_USER = $gmail
        $env:HEMOFLOW_EMAIL_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
        Write-Host "Conferindo o login no Gmail..."
        python -c "import servidor; servidor.check_email_login()"
        if ($LASTEXITCODE -eq 0) { Write-Host "Gmail conectado: a recuperacao de senha esta ativa."; return }
        Remove-Item Env:\HEMOFLOW_EMAIL_PASSWORD -ErrorAction SilentlyContinue
    }
    Remove-Item Env:\HEMOFLOW_EMAIL_USER -ErrorAction SilentlyContinue
    Write-Host "Seguindo sem e-mail: o 'Esqueceu sua senha?' fica desativado nesta sessao."
}
$teste = "import sys, servidor`ntry:`n    servidor.connect_db().close()`nexcept Exception as e:`n    print('  Erro:', e); sys.exit(1)"

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
        Configurar-Email
        $env:HEMOFLOW_PORT = "$Porta"
        python "$PSScriptRoot\servidor.py"
        exit $LASTEXITCODE
    }
    Write-Host "Nao foi possivel conectar ao MySQL (veja o erro acima). Tente novamente."
    Remove-Item Env:\HEMOFLOW_DB_PASSWORD -ErrorAction SilentlyContinue
}
Write-Host "Nao foi possivel conectar apos 5 tentativas."
Write-Host "Se esqueceu a senha do hemoflow_app, ela pode ser redefinida pelo root no MySQL Workbench."
exit 1
