-- HemoFlow — 05: endereço do doador (mesmo efeito da migração 002). Para banco NOVO e vazio.
ALTER TABLE doadores
  ADD COLUMN cep VARCHAR(9) NULL AFTER telefone,
  ADD COLUMN logradouro VARCHAR(150) NULL AFTER cep,
  ADD COLUMN numero VARCHAR(10) NULL AFTER logradouro,
  ADD COLUMN complemento VARCHAR(80) NULL AFTER numero,
  ADD COLUMN bairro VARCHAR(80) NULL AFTER complemento,
  ADD COLUMN cidade VARCHAR(80) NULL AFTER bairro,
  ADD COLUMN uf CHAR(2) NULL AFTER cidade,
  ADD INDEX idx_doadores_cidade (cidade);
