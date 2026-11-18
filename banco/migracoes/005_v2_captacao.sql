-- HemoFlow 2.0 — Migração 005: captação e fidelização de doadores.
-- Só ACRESCENTA tabelas e colunas: nenhum dado existente é alterado ou apagado. Faça backup antes.
-- Prefira scripts/migracao_005_v2.py, que pula o que já existe.
-- Reversão: banco/migracoes/005_v2_captacao_reverter.sql

-- ---------------------------------------------------------------- bancos de sangue e unidades
CREATE TABLE IF NOT EXISTS bancos_sangue (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  nome VARCHAR(150) NOT NULL,
  cnpj CHAR(14) NULL,
  cidade VARCHAR(80) NOT NULL,
  uf CHAR(2) NOT NULL,
  telefone VARCHAR(30) NULL,
  email VARCHAR(254) NULL,
  status VARCHAR(12) NOT NULL DEFAULT 'PENDENTE',
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_bancos_cnpj (cnpj),
  CONSTRAINT chk_bancos_status CHECK (status IN ('PENDENTE','ATIVO','SUSPENSO'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS unidades (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  banco_id BIGINT UNSIGNED NULL,
  nome VARCHAR(150) NOT NULL,
  tipo VARCHAR(10) NOT NULL DEFAULT 'BANCO',
  endereco VARCHAR(200) NULL,
  bairro VARCHAR(80) NULL,
  cidade VARCHAR(80) NOT NULL,
  uf CHAR(2) NOT NULL,
  horario VARCHAR(150) NULL,
  ativo TINYINT(1) NOT NULL DEFAULT 1,
  KEY idx_unidades_cidade (uf, cidade),
  CONSTRAINT fk_unidades_banco FOREIGN KEY (banco_id) REFERENCES bancos_sangue (id) ON DELETE RESTRICT,
  CONSTRAINT chk_unidades_tipo CHECK (tipo IN ('BANCO','PUBLICO'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------- termômetro (estoque informado pelo banco)
CREATE TABLE IF NOT EXISTS estoque_niveis (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  unidade_id BIGINT UNSIGNED NOT NULL,
  tipo_sanguineo VARCHAR(3) NOT NULL,
  quantidade INT NOT NULL DEFAULT 0,
  limite_critico INT NOT NULL DEFAULT 5,
  limite_atencao INT NOT NULL DEFAULT 10,
  atualizado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  atualizado_por BIGINT UNSIGNED NULL,
  editado_admin TINYINT(1) NOT NULL DEFAULT 0,
  UNIQUE KEY uq_estoque_unidade_tipo (unidade_id, tipo_sanguineo),
  CONSTRAINT fk_estoque_unidade FOREIGN KEY (unidade_id) REFERENCES unidades (id) ON DELETE CASCADE,
  CONSTRAINT chk_estoque_qtd CHECK (quantidade >= 0 AND limite_critico >= 0 AND limite_atencao >= limite_critico)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS estoque_movimentos (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  unidade_id BIGINT UNSIGNED NOT NULL,
  tipo_sanguineo VARCHAR(3) NOT NULL,
  movimento VARCHAR(8) NOT NULL,
  quantidade INT NOT NULL,
  motivo VARCHAR(200) NULL,
  usuario_id BIGINT UNSIGNED NULL,
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_movimentos_unidade (unidade_id, criado_em),
  CONSTRAINT fk_movimentos_unidade FOREIGN KEY (unidade_id) REFERENCES unidades (id) ON DELETE CASCADE,
  CONSTRAINT chk_movimento CHECK (movimento IN ('ENTRADA','SAIDA','AJUSTE'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------- agenda, convocação e doações
CREATE TABLE IF NOT EXISTS vagas (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  unidade_id BIGINT UNSIGNED NOT NULL,
  inicio DATETIME NOT NULL,
  capacidade INT NOT NULL DEFAULT 4,
  UNIQUE KEY uq_vagas_unidade_inicio (unidade_id, inicio),
  CONSTRAINT fk_vagas_unidade FOREIGN KEY (unidade_id) REFERENCES unidades (id) ON DELETE CASCADE,
  CONSTRAINT chk_vagas_capacidade CHECK (capacidade > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS convocacoes (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  banco_id BIGINT UNSIGNED NOT NULL,
  unidade_id BIGINT UNSIGNED NOT NULL,
  tipo_sanguineo VARCHAR(3) NOT NULL,
  bolsas_faltando INT NOT NULL DEFAULT 0,
  mensagem VARCHAR(500) NOT NULL,
  cidade VARCHAR(80) NOT NULL,
  uf CHAR(2) NOT NULL,
  criado_por BIGINT UNSIGNED NULL,
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_convocacoes_banco FOREIGN KEY (banco_id) REFERENCES bancos_sangue (id) ON DELETE CASCADE,
  CONSTRAINT fk_convocacoes_unidade FOREIGN KEY (unidade_id) REFERENCES unidades (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS convocacao_doadores (
  convocacao_id BIGINT UNSIGNED NOT NULL,
  doador_id BIGINT UNSIGNED NOT NULL,
  status VARCHAR(10) NOT NULL DEFAULT 'ENVIADA',
  enviada_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (convocacao_id, doador_id),
  KEY idx_convocados_doador (doador_id),
  CONSTRAINT fk_convocados_convocacao FOREIGN KEY (convocacao_id) REFERENCES convocacoes (id) ON DELETE CASCADE,
  CONSTRAINT fk_convocados_doador FOREIGN KEY (doador_id) REFERENCES doadores (id) ON DELETE CASCADE,
  CONSTRAINT chk_convocados_status CHECK (status IN ('ENVIADA','AGENDOU','RECUSOU'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS agenda_doacoes (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  doador_id BIGINT UNSIGNED NOT NULL,
  unidade_id BIGINT UNSIGNED NOT NULL,
  vaga_id BIGINT UNSIGNED NOT NULL,
  convocacao_id BIGINT UNSIGNED NULL,
  origem VARCHAR(12) NOT NULL DEFAULT 'ESPONTANEO',
  codigo CHAR(6) NOT NULL,
  status VARCHAR(12) NOT NULL DEFAULT 'AGENDADO',
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  atualizado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_agenda_doador (doador_id),
  KEY idx_agenda_codigo (codigo),
  CONSTRAINT fk_agenda_doador FOREIGN KEY (doador_id) REFERENCES doadores (id) ON DELETE CASCADE,
  CONSTRAINT fk_agenda_unidade FOREIGN KEY (unidade_id) REFERENCES unidades (id) ON DELETE CASCADE,
  CONSTRAINT fk_agenda_vaga FOREIGN KEY (vaga_id) REFERENCES vagas (id) ON DELETE CASCADE,
  CONSTRAINT fk_agenda_convocacao FOREIGN KEY (convocacao_id) REFERENCES convocacoes (id) ON DELETE SET NULL,
  CONSTRAINT chk_agenda_origem CHECK (origem IN ('CONVOCACAO','ESPONTANEO')),
  CONSTRAINT chk_agenda_status CHECK (status IN ('AGENDADO','CANCELADO','COMPARECEU','FALTOU'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS historico_doacoes (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  doador_id BIGINT UNSIGNED NOT NULL,
  unidade_id BIGINT UNSIGNED NULL,
  local_texto VARCHAR(150) NULL,
  data DATE NOT NULL,
  status VARCHAR(10) NOT NULL,
  agenda_id BIGINT UNSIGNED NULL,
  confirmado_por BIGINT UNSIGNED NULL,
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_historico_doador (doador_id, data),
  CONSTRAINT fk_historico_doador FOREIGN KEY (doador_id) REFERENCES doadores (id) ON DELETE CASCADE,
  CONSTRAINT fk_historico_unidade FOREIGN KEY (unidade_id) REFERENCES unidades (id) ON DELETE SET NULL,
  CONSTRAINT fk_historico_agenda FOREIGN KEY (agenda_id) REFERENCES agenda_doacoes (id) ON DELETE SET NULL,
  CONSTRAINT chk_historico_status CHECK (status IN ('VERIFICADA','DECLARADA'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------- parceiros, ofertas, cupons e grupos
CREATE TABLE IF NOT EXISTS parceiros (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  nome VARCHAR(150) NOT NULL,
  tipo VARCHAR(20) NOT NULL,
  cnpj CHAR(14) NULL,
  cidade VARCHAR(80) NOT NULL,
  uf CHAR(2) NOT NULL,
  endereco VARCHAR(200) NULL,
  codigo_alunos VARCHAR(20) NULL,
  status VARCHAR(12) NOT NULL DEFAULT 'PENDENTE',
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_parceiros_codigo (codigo_alunos),
  CONSTRAINT chk_parceiros_tipo CHECK (tipo IN ('COMERCIO','CURSINHO_CONCURSO','PRE_ENEM','FACULDADE','OUTRO')),
  CONSTRAINT chk_parceiros_status CHECK (status IN ('PENDENTE','ATIVO','SUSPENSO'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS doador_parceiros (
  doador_id BIGINT UNSIGNED NOT NULL,
  parceiro_id BIGINT UNSIGNED NOT NULL,
  vinculado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (doador_id, parceiro_id),
  CONSTRAINT fk_dp_doador FOREIGN KEY (doador_id) REFERENCES doadores (id) ON DELETE CASCADE,
  CONSTRAINT fk_dp_parceiro FOREIGN KEY (parceiro_id) REFERENCES parceiros (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ofertas (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  parceiro_id BIGINT UNSIGNED NOT NULL,
  titulo VARCHAR(120) NOT NULL,
  descricao VARCHAR(400) NULL,
  validade DATE NULL,
  destaque TINYINT(1) NOT NULL DEFAULT 0,
  status VARCHAR(10) NOT NULL DEFAULT 'PENDENTE',
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_ofertas_parceiro FOREIGN KEY (parceiro_id) REFERENCES parceiros (id) ON DELETE CASCADE,
  CONSTRAINT chk_ofertas_status CHECK (status IN ('PENDENTE','APROVADA','RECUSADA'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cupons (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  oferta_id BIGINT UNSIGNED NOT NULL,
  doador_id BIGINT UNSIGNED NOT NULL,
  codigo VARCHAR(12) NOT NULL,
  expira_em DATE NOT NULL,
  usado_em DATETIME NULL,
  validado_por BIGINT UNSIGNED NULL,
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_cupons_codigo (codigo),
  KEY idx_cupons_doador (doador_id),
  CONSTRAINT fk_cupons_oferta FOREIGN KEY (oferta_id) REFERENCES ofertas (id) ON DELETE CASCADE,
  CONSTRAINT fk_cupons_doador FOREIGN KEY (doador_id) REFERENCES doadores (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS grupos (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  nome VARCHAR(120) NOT NULL,
  codigo VARCHAR(12) NOT NULL,
  meta INT NOT NULL DEFAULT 10,
  criado_por BIGINT UNSIGNED NULL,
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_grupos_codigo (codigo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS grupo_membros (
  grupo_id BIGINT UNSIGNED NOT NULL,
  doador_id BIGINT UNSIGNED NOT NULL,
  entrou_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (grupo_id, doador_id),
  CONSTRAINT fk_gm_grupo FOREIGN KEY (grupo_id) REFERENCES grupos (id) ON DELETE CASCADE,
  CONSTRAINT fk_gm_doador FOREIGN KEY (doador_id) REFERENCES doadores (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------- benefícios, avisos e login por código
CREATE TABLE IF NOT EXISTS beneficios_estado (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  uf CHAR(2) NULL,
  titulo VARCHAR(150) NOT NULL,
  descricao VARCHAR(400) NOT NULL,
  minimo_homens INT NULL,
  minimo_mulheres INT NULL,
  janela_meses INT NULL,
  ativo TINYINT(1) NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS avisos (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  usuario_id BIGINT UNSIGNED NOT NULL,
  titulo VARCHAR(160) NOT NULL,
  mensagem VARCHAR(500) NOT NULL,
  link VARCHAR(80) NULL,
  lido_em DATETIME NULL,
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_avisos_usuario (usuario_id, lido_em),
  CONSTRAINT fk_avisos_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS codigos_login (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  usuario_id BIGINT UNSIGNED NOT NULL,
  codigo_hash CHAR(64) NOT NULL,
  expira_em DATETIME NOT NULL,
  usado_em DATETIME NULL,
  tentativas INT NOT NULL DEFAULT 0,
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_codigos_usuario (usuario_id),
  CONSTRAINT fk_codigos_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------- colunas novas (o script Python pula as que já existem)
ALTER TABLE usuarios ADD COLUMN banco_id BIGINT UNSIGNED NULL, ADD COLUMN parceiro_id BIGINT UNSIGNED NULL,
  ADD CONSTRAINT fk_usuarios_banco FOREIGN KEY (banco_id) REFERENCES bancos_sangue (id) ON DELETE SET NULL,
  ADD CONSTRAINT fk_usuarios_parceiro FOREIGN KEY (parceiro_id) REFERENCES parceiros (id) ON DELETE SET NULL;

ALTER TABLE doadores
  ADD COLUMN usuario_id BIGINT UNSIGNED NULL,
  ADD COLUMN sexo CHAR(1) NULL,
  ADD COLUMN ultima_doacao_informada DATE NULL,
  ADD COLUMN consentimento_convocacao TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN consentimento_em DATETIME NULL,
  ADD COLUMN responsavel_nome VARCHAR(120) NULL,
  ADD COLUMN responsavel_consentiu TINYINT(1) NOT NULL DEFAULT 0,
  ADD UNIQUE KEY uq_doadores_usuario (usuario_id),
  ADD CONSTRAINT fk_doadores_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE SET NULL;

-- ---------------------------------------------------------------- dados de referência
INSERT IGNORE INTO perfis (nome, descricao, sistema) VALUES
  ('BANCO', 'Equipe de captação de um banco de sangue privado', 1),
  ('PARCEIRO', 'Parceiro: comércio, cursinho, pré-Enem ou faculdade', 1),
  ('DOADOR', 'Doador de sangue (app)', 1);
