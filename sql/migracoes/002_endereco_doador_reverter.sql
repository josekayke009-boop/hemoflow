-- HemoFlow — Reverte a migração 002.
-- ATENÇÃO: APAGA as colunas de endereço e os endereços gravados nelas. Faça backup antes.
USE hemoflow;
ALTER TABLE doadores
  DROP INDEX idx_doadores_cidade,
  DROP COLUMN uf, DROP COLUMN cidade, DROP COLUMN bairro, DROP COLUMN complemento,
  DROP COLUMN numero, DROP COLUMN logradouro, DROP COLUMN cep;
