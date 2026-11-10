# HemoFlow — backup completo + auditoria SOMENTE LEITURA do banco MySQL.
# Não altera nada no banco. A senha é pedida sem aparecer na tela e não é gravada.
#
# Uso (PowerShell, na pasta do projeto):
#   .\scripts\auditar_e_backup_banco.ps1                 (usuário root)
#   .\scripts\auditar_e_backup_banco.ps1 -Usuario outro
#
# Gera em ..\HemoFlow_backups\banco_<data>\ :
#   hemoflow_completo.sql   -> backup completo (estrutura + dados), restaurável
#   hemoflow_estrutura.sql  -> só a estrutura (base para criar o banco na nuvem)
#   auditoria.txt           -> tabelas, contagens, chaves, índices, duplicidades, permissões
#                              (sem e-mails, nomes ou outros dados pessoais)
param(
    [string]$Usuario = "root",
    [string]$Servidor = "127.0.0.1",
    [int]$Porta = 3306,
    [string]$Banco = "hemoflow"
)
$ErrorActionPreference = "Stop"
$bin = "C:\Program Files\MySQL\MySQL Server 8.0\bin"
$mysql = Join-Path $bin "mysql.exe"
$dump = Join-Path $bin "mysqldump.exe"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$out = Join-Path (Split-Path $PSScriptRoot -Parent | Split-Path -Parent) "HemoFlow_backups\banco_$ts"
New-Item -ItemType Directory -Force $out | Out-Null

$sec = Read-Host "Senha do MySQL para '$Usuario'" -AsSecureString
$env:MYSQL_PWD = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
$common = @("--host=$Servidor", "--port=$Porta", "--user=$Usuario", "--default-character-set=utf8mb4")

try {
    Write-Host "1/3 Backup completo..."
    & $dump @common --single-transaction --routines --triggers --events --hex-blob `
        --set-gtid-purged=OFF --databases $Banco --result-file="$out\hemoflow_completo.sql"
    if ($LASTEXITCODE -ne 0) { throw "mysqldump (completo) falhou." }

    Write-Host "2/3 Estrutura..."
    & $dump @common --no-data --routines --triggers --events --set-gtid-purged=OFF `
        --databases $Banco --result-file="$out\hemoflow_estrutura.sql"
    if ($LASTEXITCODE -ne 0) { throw "mysqldump (estrutura) falhou." }

    Write-Host "3/3 Auditoria (somente leitura)..."
    $sql = @"
SELECT VERSION() AS versao_mysql, @@sql_mode AS sql_mode, @@time_zone AS fuso, @@character_set_server AS charset;
SELECT TABLE_NAME AS tabela, ENGINE, TABLE_ROWS AS linhas_aprox, TABLE_COLLATION
  FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='$Banco' ORDER BY TABLE_NAME;
SELECT TABLE_NAME AS tabela, COLUMN_NAME AS coluna, COLUMN_TYPE AS tipo, IS_NULLABLE AS nulo, COLUMN_KEY AS chave
  FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='$Banco' ORDER BY TABLE_NAME, ORDINAL_POSITION;
SELECT TABLE_NAME AS tabela, CONSTRAINT_NAME AS fk, COLUMN_NAME AS coluna, REFERENCED_TABLE_NAME AS ref_tabela, REFERENCED_COLUMN_NAME AS ref_coluna
  FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA='$Banco' AND REFERENCED_TABLE_NAME IS NOT NULL ORDER BY TABLE_NAME;
SELECT TABLE_NAME AS tabela, INDEX_NAME AS indice, NON_UNIQUE, GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) AS colunas
  FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA='$Banco' GROUP BY TABLE_NAME, INDEX_NAME, NON_UNIQUE ORDER BY TABLE_NAME, INDEX_NAME;
SELECT TABLE_NAME AS tabela, CONSTRAINT_NAME AS regra, CHECK_CLAUSE
  FROM INFORMATION_SCHEMA.CHECK_CONSTRAINTS cc JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc USING (CONSTRAINT_SCHEMA, CONSTRAINT_NAME)
  WHERE CONSTRAINT_SCHEMA='$Banco';
SELECT 'doadores: e-mails repetidos (grupos)' AS verificacao, COUNT(*) AS qtd FROM (SELECT LOWER(TRIM(email)) e FROM $Banco.doadores WHERE email IS NOT NULL GROUP BY e HAVING COUNT(*)>1) x
UNION ALL SELECT 'usuarios: e-mails repetidos (grupos)', COUNT(*) FROM (SELECT LOWER(TRIM(email)) e FROM $Banco.usuarios GROUP BY e HAVING COUNT(*)>1) y
UNION ALL SELECT 'usuarios sem perfil', COUNT(*) FROM $Banco.usuarios u WHERE NOT EXISTS (SELECT 1 FROM $Banco.usuario_perfis up WHERE up.usuario_id=u.id)
UNION ALL SELECT 'usuarios com mais de 1 perfil', COUNT(*) FROM (SELECT usuario_id FROM $Banco.usuario_perfis GROUP BY usuario_id HAVING COUNT(*)>1) z
UNION ALL SELECT 'perfis cadastrados', COUNT(*) FROM $Banco.perfis
UNION ALL SELECT 'permissoes cadastradas', COUNT(*) FROM $Banco.permissoes;
SELECT pf.nome AS perfil, COUNT(pp.permissao_id) AS qtd_permissoes, GROUP_CONCAT(p.codigo ORDER BY p.codigo) AS permissoes
  FROM $Banco.perfis pf LEFT JOIN $Banco.perfil_permissoes pp ON pp.perfil_id=pf.id LEFT JOIN $Banco.permissoes p ON p.id=pp.permissao_id
  GROUP BY pf.id, pf.nome ORDER BY pf.id;
SELECT user, host, plugin, account_locked FROM mysql.user WHERE user LIKE 'hemoflow%';
SHOW GRANTS FOR 'hemoflow_app'@'localhost';
"@
    $sql | & $mysql @common --table --force $Banco 2>&1 | Out-File -Encoding utf8 "$out\auditoria.txt"

    Write-Host "`nConcluído. Arquivos em: $out"
    Get-ChildItem $out | Format-Table Name, Length -AutoSize
    Write-Host "ATENÇÃO: hemoflow_completo.sql contém os dados do banco. Não envie para o GitHub nem compartilhe."
}
finally {
    Remove-Item Env:\MYSQL_PWD -ErrorAction SilentlyContinue
}
