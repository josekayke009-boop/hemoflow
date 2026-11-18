-- HemoFlow — Reverte a migração 005 (HemoFlow 2.0).
-- ATENÇÃO: APAGA todas as tabelas e colunas da versão 2.0 e os dados gravados nelas. Faça backup antes.
ALTER TABLE doadores DROP FOREIGN KEY fk_doadores_usuario, DROP INDEX uq_doadores_usuario,
  DROP COLUMN usuario_id, DROP COLUMN sexo, DROP COLUMN ultima_doacao_informada, DROP COLUMN consentimento_convocacao,
  DROP COLUMN consentimento_em, DROP COLUMN responsavel_nome, DROP COLUMN responsavel_consentiu;
ALTER TABLE usuarios DROP FOREIGN KEY fk_usuarios_banco, DROP FOREIGN KEY fk_usuarios_parceiro,
  DROP COLUMN banco_id, DROP COLUMN parceiro_id;
DROP TABLE IF EXISTS codigos_login, avisos, beneficios_estado, grupo_membros, grupos, cupons, ofertas,
  doador_parceiros, parceiros, historico_doacoes, agenda_doacoes, convocacao_doadores, convocacoes, vagas,
  estoque_movimentos, estoque_niveis, unidades, bancos_sangue;
DELETE FROM perfis WHERE nome IN ('BANCO', 'PARCEIRO', 'DOADOR');
