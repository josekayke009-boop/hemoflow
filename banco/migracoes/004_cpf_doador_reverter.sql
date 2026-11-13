-- HemoFlow — Reverte a migração 004.
-- ATENÇÃO: APAGA a coluna de CPF e os CPFs gravados nela. Faça backup antes.
USE hemoflow;
ALTER TABLE doadores
  DROP INDEX uq_doadores_cpf,
  DROP COLUMN cpf;
