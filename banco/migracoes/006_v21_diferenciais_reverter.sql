-- Desfaz a migração 006 (faça backup antes). Apaga as declarações emitidas.
DROP TABLE IF EXISTS declaracoes;
ALTER TABLE ofertas DROP COLUMN tipo_emergencia, DROP COLUMN emergencia_ate;
