-- HemoFlow — Migração 002: endereço do doador.
-- Referência SQL. Prefira scripts/migracao_002_endereco_doador.py (não repete passos já aplicados).
-- Só acrescenta colunas vazias (NULL): nenhum dado é alterado. Faça backup antes.
-- Reversão: sql/migracoes/002_endereco_doador_reverter.sql
USE hemoflow;
ALTER TABLE doadores
  ADD COLUMN cep VARCHAR(9) NULL AFTER telefone,
  ADD COLUMN logradouro VARCHAR(150) NULL AFTER cep,
  ADD COLUMN numero VARCHAR(10) NULL AFTER logradouro,
  ADD COLUMN complemento VARCHAR(80) NULL AFTER numero,
  ADD COLUMN bairro VARCHAR(80) NULL AFTER complemento,
  ADD COLUMN cidade VARCHAR(80) NULL AFTER bairro,
  ADD COLUMN uf CHAR(2) NULL AFTER cidade,
  ADD INDEX idx_doadores_cidade (cidade);
