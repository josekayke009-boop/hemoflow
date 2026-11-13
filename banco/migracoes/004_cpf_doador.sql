-- HemoFlow — Migração 004: CPF do doador (somente números, único).
-- Referência SQL. Prefira scripts/migracao_004_cpf_doador.py (não repete passos já aplicados).
-- Só acrescenta uma coluna vazia (NULL): nenhum dado é alterado. Faça backup antes.
-- Doadores antigos ficam sem CPF (NULL); o UNIQUE aceita vários NULL.
-- Reversão: banco/migracoes/004_cpf_doador_reverter.sql
USE hemoflow;
ALTER TABLE doadores
  ADD COLUMN cpf CHAR(11) NULL AFTER nome,
  ADD UNIQUE KEY uq_doadores_cpf (cpf);
