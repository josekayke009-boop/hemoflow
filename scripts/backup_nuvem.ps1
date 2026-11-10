# HemoFlow — backup do banco MySQL da NUVEM para o seu computador.
# Complementa o backup automático do provedor (tenha os dois).
# Não altera nada no banco. A senha é pedida sem aparecer e não é gravada.
#
# Uso:
#   .\scripts\backup_nuvem.ps1 -Servidor host-do-provedor -Porta 3306 -Usuario usuario -Banco hemoflow
#
# Gera ..\HemoFlow_backups\nuvem_<data>\hemoflow_nuvem.sql (CONTÉM DADOS: não compartilhe).
# Restaurar (num banco vazio):  mysql -h HOST -P PORTA -u USUARIO -p --ssl-mode=REQUIRED BANCO < arquivo.sql
param(
    [Parameter(Mandatory = $true)][string]$Servidor,
    [int]$Porta = 3306,
    [Parameter(Mandatory = $true)][string]$Usuario,
    [string]$Banco = "hemoflow"
)
$ErrorActionPreference = "Stop"
$dump = "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$out = Join-Path (Split-Path $PSScriptRoot -Parent | Split-Path -Parent) "HemoFlow_backups\nuvem_$ts"
New-Item -ItemType Directory -Force $out | Out-Null

$sec = Read-Host "Senha do MySQL da nuvem para '$Usuario'" -AsSecureString
$env:MYSQL_PWD = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
try {
    & $dump "--host=$Servidor" "--port=$Porta" "--user=$Usuario" --ssl-mode=REQUIRED `
        --default-character-set=utf8mb4 --single-transaction --routines --triggers `
        --set-gtid-purged=OFF --no-tablespaces --column-statistics=0 $Banco `
        --result-file="$out\hemoflow_nuvem.sql"
    if ($LASTEXITCODE -ne 0) { throw "mysqldump falhou." }
    Get-ChildItem $out | Format-Table Name, Length -AutoSize
    Write-Host "Backup salvo em $out. Ele contém dados: não envie para o GitHub."
}
finally {
    Remove-Item Env:\MYSQL_PWD -ErrorAction SilentlyContinue
}
