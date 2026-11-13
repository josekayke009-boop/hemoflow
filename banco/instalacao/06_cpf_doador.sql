-- HemoFlow — 06: CPF do doador (mesmo efeito da migração 004). Para banco NOVO e vazio.
ALTER TABLE doadores
  ADD COLUMN cpf CHAR(11) NULL AFTER nome,
  ADD UNIQUE KEY uq_doadores_cpf (cpf);
