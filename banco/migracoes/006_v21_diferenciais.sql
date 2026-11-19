-- HemoFlow 2.1 — diferenciais (só ACRESCENTA; nada existente é alterado ou apagado)
-- 1) Oferta de emergência: o parceiro destaca uma oferta para um tipo sanguíneo em falta por 7 dias
--    (colunas ofertas.tipo_emergencia e ofertas.emergencia_ate, criadas pelo script migracao_006_v21.py)
-- 2) Declarações de doação para alunos de cursinhos e faculdades parceiras, com código de verificação
CREATE TABLE IF NOT EXISTS declaracoes (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  codigo CHAR(10) NOT NULL,
  doador_id BIGINT UNSIGNED NOT NULL,
  parceiro_id BIGINT UNSIGNED NOT NULL,
  total_doacoes INT NOT NULL,
  ultima_doacao DATE NULL,
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_declaracoes_codigo (codigo),
  KEY idx_declaracoes_doador (doador_id),
  CONSTRAINT fk_declaracoes_doador FOREIGN KEY (doador_id) REFERENCES doadores (id) ON DELETE CASCADE,
  CONSTRAINT fk_declaracoes_parceiro FOREIGN KEY (parceiro_id) REFERENCES parceiros (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
