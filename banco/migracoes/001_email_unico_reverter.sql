-- HemoFlow — Reverte a migração 001.
-- ATENÇÃO: o passo 2 APAGA a coluna profissionais.email e os e-mails gravados nela.
-- Faça backup antes. Executar com usuário administrativo.

USE hemoflow;

-- 1) Remove a unicidade dos e-mails de doadores (os dados permanecem).
ALTER TABLE doadores DROP INDEX uq_doadores_email;

-- 2) Remove a unicidade e a coluna de e-mail dos profissionais.
ALTER TABLE profissionais DROP INDEX uq_profissionais_email;
ALTER TABLE profissionais DROP COLUMN email;
