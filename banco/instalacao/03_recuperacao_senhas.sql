-- HemoFlow — 03: instala a tabela de recuperação de senha.
-- NÃO DESTRUTIVO: só cria a tabela se ela ainda não existir; não altera nem apaga dados.
-- Precisa ser executado UMA vez por um usuário com privilégio CREATE (ex.: root),
-- porque o usuário da aplicação (hemoflow_app) não tem esse privilégio.
--


CREATE TABLE IF NOT EXISTS recuperacao_senhas (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    usuario_id BIGINT UNSIGNED NOT NULL,
    token_hash CHAR(64) NOT NULL,
    expira_em DATETIME NOT NULL,
    usado_em DATETIME NULL,
    criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_recuperacao_token UNIQUE (token_hash),
    INDEX idx_recuperacao_usuario (usuario_id),
    INDEX idx_recuperacao_expira (expira_em),
    CONSTRAINT fk_recuperacao_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
