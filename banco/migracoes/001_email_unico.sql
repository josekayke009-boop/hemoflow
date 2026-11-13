-- HemoFlow — Migração 001: e-mail único em doadores e profissionais.
-- Referência SQL. Prefira executar scripts/migracao_001_email_unico.py, que confere
-- duplicidades antes e não repete passos já aplicados.
--
-- PRÉ-REQUISITOS
--   1. Backup feito (scripts/auditar_e_backup_banco.ps1).
--   2. Executar com usuário administrativo (ex.: root): hemoflow_app não tem ALTER.
--   3. A consulta abaixo deve retornar ZERO linhas; se retornar, resolva os duplicados antes.
--
-- Reversão: sql/migracoes/001_email_unico_reverter.sql

USE hemoflow;

-- Conferência (não altera nada):
SELECT LOWER(TRIM(email)) AS email_normalizado, COUNT(*) AS qtd, GROUP_CONCAT(id) AS ids
FROM doadores WHERE email IS NOT NULL
GROUP BY LOWER(TRIM(email)) HAVING COUNT(*) > 1;

-- 1) Doadores: um e-mail só pode pertencer a um doador.
ALTER TABLE doadores ADD CONSTRAINT uq_doadores_email UNIQUE (email);

-- 2) Profissionais: nova coluna de e-mail (NULL para os registros antigos) + unicidade.
ALTER TABLE profissionais ADD COLUMN email VARCHAR(254) NULL AFTER nome;
ALTER TABLE profissionais ADD CONSTRAINT uq_profissionais_email UNIQUE (email);
