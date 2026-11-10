-- HemoFlow — 04: e-mail único em doadores e profissionais (mesmo efeito da migração 001).
-- Para banco NOVO e vazio. Num banco já existente use scripts/migracao_001_email_unico.py.
ALTER TABLE doadores ADD CONSTRAINT uq_doadores_email UNIQUE (email);
ALTER TABLE profissionais ADD COLUMN email VARCHAR(254) NULL AFTER nome;
ALTER TABLE profissionais ADD CONSTRAINT uq_profissionais_email UNIQUE (email);
