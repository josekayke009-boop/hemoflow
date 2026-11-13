-- HemoFlow — 01: estrutura do banco (26 tabelas), gerada do MySQL local em 10/11/2026.
-- Sem dados. Sem DROP TABLE: não apaga nada se for executado num banco existente.
-- Execute no banco de destino já selecionado (não cria nem troca de banco).
-- MySQL dump 10.13  Distrib 8.0.46, for Win64 (x86_64)
--
-- ------------------------------------------------------
-- Server version	8.0.46

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Current Database: `hemoflow`
--



--
-- Table structure for table `agendamentos`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `agendamentos` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `doador_id` bigint unsigned NOT NULL,
  `data_hora` datetime NOT NULL,
  `status` varchar(20) NOT NULL DEFAULT 'AGENDADO',
  `observacoes` text,
  `criado_por` bigint unsigned NOT NULL,
  `criado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `atualizado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `fk_agendamentos_criador` (`criado_por`),
  KEY `idx_agendamentos_data_status` (`data_hora`,`status`),
  KEY `idx_agendamentos_doador_data` (`doador_id`,`data_hora`),
  CONSTRAINT `fk_agendamentos_criador` FOREIGN KEY (`criado_por`) REFERENCES `usuarios` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_agendamentos_doador` FOREIGN KEY (`doador_id`) REFERENCES `doadores` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_agendamentos_status` CHECK ((`status` in (_utf8mb4'AGENDADO',_utf8mb4'CONFIRMADO',_utf8mb4'REALIZADO',_utf8mb4'CANCELADO',_utf8mb4'FALTOU')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `alertas`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `alertas` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `regra_id` bigint unsigned DEFAULT NULL,
  `bolsa_id` bigint unsigned DEFAULT NULL,
  `tipo_sanguineo_id` bigint unsigned DEFAULT NULL,
  `chave_ocorrencia` varchar(160) NOT NULL,
  `mensagem` varchar(500) NOT NULL,
  `prioridade` varchar(15) NOT NULL DEFAULT 'MEDIA',
  `status` varchar(20) NOT NULL DEFAULT 'ABERTO',
  `gerado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `reconhecido_por` bigint unsigned DEFAULT NULL,
  `reconhecido_em` datetime DEFAULT NULL,
  `resolvido_em` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_alertas_chave_ocorrencia` (`chave_ocorrencia`),
  KEY `fk_alertas_regra` (`regra_id`),
  KEY `fk_alertas_reconhecedor` (`reconhecido_por`),
  KEY `idx_alertas_status_prioridade_data` (`status`,`prioridade`,`gerado_em`),
  KEY `idx_alertas_bolsa` (`bolsa_id`),
  KEY `idx_alertas_tipo` (`tipo_sanguineo_id`),
  CONSTRAINT `fk_alertas_bolsa` FOREIGN KEY (`bolsa_id`) REFERENCES `bolsas` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_alertas_reconhecedor` FOREIGN KEY (`reconhecido_por`) REFERENCES `usuarios` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `fk_alertas_regra` FOREIGN KEY (`regra_id`) REFERENCES `regras_alerta` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_alertas_tipo` FOREIGN KEY (`tipo_sanguineo_id`) REFERENCES `tipos_sanguineos` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_alertas_prioridade` CHECK ((`prioridade` in (_utf8mb4'BAIXA',_utf8mb4'MEDIA',_utf8mb4'ALTA',_utf8mb4'CRITICA'))),
  CONSTRAINT `chk_alertas_status` CHECK ((`status` in (_utf8mb4'ABERTO',_utf8mb4'RECONHECIDO',_utf8mb4'RESOLVIDO',_utf8mb4'CANCELADO')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `bolsas`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `bolsas` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `codigo` varchar(40) NOT NULL,
  `tipo_sanguineo_id` bigint unsigned NOT NULL,
  `hemocomponente_id` bigint unsigned NOT NULL,
  `local_id` bigint unsigned NOT NULL,
  `doacao_id` bigint unsigned DEFAULT NULL,
  `volume_ml` smallint unsigned NOT NULL,
  `data_coleta` date NOT NULL,
  `data_validade` date NOT NULL,
  `status` varchar(20) NOT NULL DEFAULT 'DISPONIVEL',
  `observacoes` text,
  `criado_por` bigint unsigned NOT NULL,
  `criado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `atualizado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_bolsas_codigo` (`codigo`),
  KEY `fk_bolsas_criador` (`criado_por`),
  KEY `idx_bolsas_tipo_status` (`tipo_sanguineo_id`,`status`),
  KEY `idx_bolsas_validade_status` (`data_validade`,`status`),
  KEY `idx_bolsas_local_status` (`local_id`,`status`),
  KEY `idx_bolsas_componente_status` (`hemocomponente_id`,`status`),
  KEY `idx_bolsas_doacao` (`doacao_id`),
  CONSTRAINT `fk_bolsas_componente` FOREIGN KEY (`hemocomponente_id`) REFERENCES `hemocomponentes` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_bolsas_criador` FOREIGN KEY (`criado_por`) REFERENCES `usuarios` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_bolsas_doacao` FOREIGN KEY (`doacao_id`) REFERENCES `doacoes` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_bolsas_local` FOREIGN KEY (`local_id`) REFERENCES `locais_armazenamento` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_bolsas_tipo` FOREIGN KEY (`tipo_sanguineo_id`) REFERENCES `tipos_sanguineos` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_bolsas_datas` CHECK ((`data_validade` >= `data_coleta`)),
  CONSTRAINT `chk_bolsas_status` CHECK ((`status` in (_utf8mb4'DISPONIVEL',_utf8mb4'RESERVADA',_utf8mb4'TRANSFUNDIDA',_utf8mb4'DESCARTADA',_utf8mb4'QUARENTENA'))),
  CONSTRAINT `chk_bolsas_volume` CHECK (((`volume_ml` > 0) and (`volume_ml` <= 1000)))
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `configuracoes`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `configuracoes` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `chave` varchar(100) NOT NULL,
  `valor_json` json NOT NULL,
  `descricao` varchar(255) DEFAULT NULL,
  `atualizado_por` bigint unsigned DEFAULT NULL,
  `atualizado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_configuracoes_chave` (`chave`),
  KEY `fk_configuracoes_usuario` (`atualizado_por`),
  CONSTRAINT `fk_configuracoes_usuario` FOREIGN KEY (`atualizado_por`) REFERENCES `usuarios` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `descartes`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `descartes` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `bolsa_id` bigint unsigned NOT NULL,
  `motivo_codigo` varchar(40) NOT NULL,
  `justificativa` text NOT NULL,
  `descartada_por` bigint unsigned NOT NULL,
  `descartada_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_descartes_bolsa` (`bolsa_id`),
  KEY `fk_descartes_usuario` (`descartada_por`),
  KEY `idx_descartes_data` (`descartada_em`),
  CONSTRAINT `fk_descartes_bolsa` FOREIGN KEY (`bolsa_id`) REFERENCES `bolsas` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_descartes_usuario` FOREIGN KEY (`descartada_por`) REFERENCES `usuarios` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_descartes_motivo` CHECK ((`motivo_codigo` in (_utf8mb4'VENCIMENTO',_utf8mb4'AVARIA',_utf8mb4'CONTAMINACAO_SUSPEITA',_utf8mb4'FALHA_ARMAZENAMENTO',_utf8mb4'OUTRO')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `doacoes`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `doacoes` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `doador_id` bigint unsigned NOT NULL,
  `agendamento_id` bigint unsigned DEFAULT NULL,
  `profissional_id` bigint unsigned DEFAULT NULL,
  `data_hora` datetime NOT NULL,
  `volume_ml` smallint unsigned NOT NULL,
  `status` varchar(20) NOT NULL DEFAULT 'REGISTRADA',
  `observacoes` text,
  `registrado_por` bigint unsigned NOT NULL,
  `criado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `fk_doacoes_agendamento` (`agendamento_id`),
  KEY `fk_doacoes_profissional` (`profissional_id`),
  KEY `fk_doacoes_registrador` (`registrado_por`),
  KEY `idx_doacoes_doador_data` (`doador_id`,`data_hora`),
  KEY `idx_doacoes_data_status` (`data_hora`,`status`),
  CONSTRAINT `fk_doacoes_agendamento` FOREIGN KEY (`agendamento_id`) REFERENCES `agendamentos` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_doacoes_doador` FOREIGN KEY (`doador_id`) REFERENCES `doadores` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_doacoes_profissional` FOREIGN KEY (`profissional_id`) REFERENCES `profissionais` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_doacoes_registrador` FOREIGN KEY (`registrado_por`) REFERENCES `usuarios` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_doacoes_status` CHECK ((`status` in (_utf8mb4'REGISTRADA',_utf8mb4'CANCELADA',_utf8mb4'EM_REVISAO'))),
  CONSTRAINT `chk_doacoes_volume` CHECK ((`volume_ml` > 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `doadores`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `doadores` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `nome` varchar(120) NOT NULL,
  `data_nascimento` date DEFAULT NULL,
  `email` varchar(254) DEFAULT NULL,
  `telefone` varchar(30) DEFAULT NULL,
  `codigo_ficticio` varchar(40) DEFAULT NULL,
  `status` varchar(20) NOT NULL DEFAULT 'ATIVO',
  `observacoes` text,
  `criado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `atualizado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `tipo_sanguineo` varchar(3) DEFAULT NULL,
  `peso_kg` decimal(5,2) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_doadores_codigo_ficticio` (`codigo_ficticio`),
  KEY `idx_doadores_nome` (`nome`),
  KEY `idx_doadores_status_nome` (`status`,`nome`),
  KEY `idx_doadores_email` (`email`),
  CONSTRAINT `chk_doadores_status` CHECK ((`status` in (_utf8mb4'ATIVO',_utf8mb4'INATIVO',_utf8mb4'BLOQUEADO')))
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `execucoes_relatorios`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `execucoes_relatorios` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `tipo_relatorio` varchar(80) NOT NULL,
  `parametros_json` json DEFAULT NULL,
  `status` varchar(20) NOT NULL DEFAULT 'SOLICITADO',
  `arquivo_referencia` varchar(500) DEFAULT NULL,
  `solicitado_por` bigint unsigned NOT NULL,
  `solicitado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `concluido_em` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_relatorios_status_data` (`status`,`solicitado_em`),
  KEY `idx_relatorios_usuario_data` (`solicitado_por`,`solicitado_em`),
  CONSTRAINT `fk_relatorios_usuario` FOREIGN KEY (`solicitado_por`) REFERENCES `usuarios` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_relatorios_status` CHECK ((`status` in (_utf8mb4'SOLICITADO',_utf8mb4'PROCESSANDO',_utf8mb4'CONCLUIDO',_utf8mb4'FALHOU',_utf8mb4'CANCELADO')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `hemocomponentes`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `hemocomponentes` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `codigo` varchar(30) NOT NULL,
  `nome` varchar(100) NOT NULL,
  `descricao` varchar(255) DEFAULT NULL,
  `ativo` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_hemocomponentes_codigo` (`codigo`),
  UNIQUE KEY `uq_hemocomponentes_nome` (`nome`)
) ENGINE=InnoDB AUTO_INCREMENT=98 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `historico_auditoria`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `historico_auditoria` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `usuario_id` bigint unsigned DEFAULT NULL,
  `acao` varchar(80) NOT NULL,
  `modulo` varchar(60) NOT NULL,
  `entidade` varchar(80) NOT NULL,
  `entidade_id` varchar(80) DEFAULT NULL,
  `detalhes_json` json DEFAULT NULL,
  `ip_origem` varchar(45) DEFAULT NULL,
  `criado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `fk_auditoria_usuario` (`usuario_id`),
  KEY `idx_auditoria_data` (`criado_em`),
  KEY `idx_auditoria_modulo_data` (`modulo`,`criado_em`),
  KEY `idx_auditoria_entidade` (`entidade`,`entidade_id`),
  CONSTRAINT `fk_auditoria_usuario` FOREIGN KEY (`usuario_id`) REFERENCES `usuarios` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `limites_estoque`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `limites_estoque` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `tipo_sanguineo_id` bigint unsigned NOT NULL,
  `hemocomponente_id` bigint unsigned NOT NULL,
  `local_id` bigint unsigned NOT NULL,
  `quantidade_minima` int unsigned NOT NULL DEFAULT '0',
  `ativo` tinyint(1) NOT NULL DEFAULT '1',
  `atualizado_por` bigint unsigned DEFAULT NULL,
  `atualizado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_limite_estoque_dimensoes` (`tipo_sanguineo_id`,`hemocomponente_id`,`local_id`),
  KEY `fk_limites_componente` (`hemocomponente_id`),
  KEY `fk_limites_local` (`local_id`),
  KEY `fk_limites_usuario` (`atualizado_por`),
  KEY `idx_limites_ativo` (`ativo`),
  CONSTRAINT `fk_limites_componente` FOREIGN KEY (`hemocomponente_id`) REFERENCES `hemocomponentes` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_limites_local` FOREIGN KEY (`local_id`) REFERENCES `locais_armazenamento` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_limites_tipo` FOREIGN KEY (`tipo_sanguineo_id`) REFERENCES `tipos_sanguineos` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_limites_usuario` FOREIGN KEY (`atualizado_por`) REFERENCES `usuarios` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `locais_armazenamento`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `locais_armazenamento` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `nome` varchar(100) NOT NULL,
  `descricao` varchar(255) DEFAULT NULL,
  `ativo` tinyint(1) NOT NULL DEFAULT '1',
  `criado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_locais_armazenamento_nome` (`nome`)
) ENGINE=InnoDB AUTO_INCREMENT=64 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `mensagem_destinatarios`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `mensagem_destinatarios` (
  `mensagem_id` bigint unsigned NOT NULL,
  `usuario_id` bigint unsigned NOT NULL,
  `lida_em` datetime DEFAULT NULL,
  `arquivada_em` datetime DEFAULT NULL,
  PRIMARY KEY (`mensagem_id`,`usuario_id`),
  KEY `idx_msg_dest_usuario_leitura` (`usuario_id`,`lida_em`),
  CONSTRAINT `fk_msg_dest_mensagem` FOREIGN KEY (`mensagem_id`) REFERENCES `mensagens` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_msg_dest_usuario` FOREIGN KEY (`usuario_id`) REFERENCES `usuarios` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `mensagens`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `mensagens` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `remetente_id` bigint unsigned NOT NULL,
  `assunto` varchar(180) NOT NULL,
  `corpo` text NOT NULL,
  `criada_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `arquivada_em` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_mensagens_remetente_data` (`remetente_id`,`criada_em`),
  CONSTRAINT `fk_mensagens_remetente` FOREIGN KEY (`remetente_id`) REFERENCES `usuarios` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `movimentacoes_estoque`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `movimentacoes_estoque` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `bolsa_id` bigint unsigned NOT NULL,
  `tipo_movimentacao` varchar(30) NOT NULL,
  `status_anterior` varchar(20) DEFAULT NULL,
  `status_novo` varchar(20) NOT NULL,
  `local_origem_id` bigint unsigned DEFAULT NULL,
  `local_destino_id` bigint unsigned DEFAULT NULL,
  `responsavel_id` bigint unsigned NOT NULL,
  `motivo` text,
  `referencia` varchar(100) DEFAULT NULL,
  `criado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `fk_mov_estoque_origem` (`local_origem_id`),
  KEY `fk_mov_estoque_destino` (`local_destino_id`),
  KEY `idx_mov_estoque_bolsa_data` (`bolsa_id`,`criado_em`),
  KEY `idx_mov_estoque_responsavel_data` (`responsavel_id`,`criado_em`),
  KEY `idx_mov_estoque_data` (`criado_em`),
  CONSTRAINT `fk_mov_estoque_bolsa` FOREIGN KEY (`bolsa_id`) REFERENCES `bolsas` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_mov_estoque_destino` FOREIGN KEY (`local_destino_id`) REFERENCES `locais_armazenamento` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_mov_estoque_origem` FOREIGN KEY (`local_origem_id`) REFERENCES `locais_armazenamento` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_mov_estoque_responsavel` FOREIGN KEY (`responsavel_id`) REFERENCES `usuarios` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_mov_estoque_tipo` CHECK ((`tipo_movimentacao` in (_utf8mb4'ENTRADA',_utf8mb4'RESERVA',_utf8mb4'LIBERACAO',_utf8mb4'TRANSFERENCIA',_utf8mb4'TRANSFUSAO',_utf8mb4'DESCARTE',_utf8mb4'QUARENTENA',_utf8mb4'AJUSTE')))
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `notificacoes`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `notificacoes` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `usuario_id` bigint unsigned NOT NULL,
  `alerta_id` bigint unsigned DEFAULT NULL,
  `titulo` varchar(160) NOT NULL,
  `mensagem` varchar(500) NOT NULL,
  `lida_em` datetime DEFAULT NULL,
  `criada_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `fk_notificacoes_alerta` (`alerta_id`),
  KEY `idx_notificacoes_usuario_leitura_data` (`usuario_id`,`lida_em`,`criada_em`),
  CONSTRAINT `fk_notificacoes_alerta` FOREIGN KEY (`alerta_id`) REFERENCES `alertas` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_notificacoes_usuario` FOREIGN KEY (`usuario_id`) REFERENCES `usuarios` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `perfil_permissoes`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `perfil_permissoes` (
  `perfil_id` bigint unsigned NOT NULL,
  `permissao_id` bigint unsigned NOT NULL,
  PRIMARY KEY (`perfil_id`,`permissao_id`),
  KEY `idx_perfil_permissoes_permissao` (`permissao_id`),
  CONSTRAINT `fk_perfil_permissoes_perfil` FOREIGN KEY (`perfil_id`) REFERENCES `perfis` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_perfil_permissoes_permissao` FOREIGN KEY (`permissao_id`) REFERENCES `permissoes` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `perfis`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `perfis` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `nome` varchar(60) NOT NULL,
  `descricao` varchar(255) DEFAULT NULL,
  `sistema` tinyint(1) NOT NULL DEFAULT '0',
  `criado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_perfis_nome` (`nome`)
) ENGINE=InnoDB AUTO_INCREMENT=79 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `permissoes`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `permissoes` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `codigo` varchar(120) NOT NULL,
  `descricao` varchar(255) NOT NULL,
  `modulo` varchar(60) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_permissoes_codigo` (`codigo`),
  KEY `idx_permissoes_modulo` (`modulo`)
) ENGINE=InnoDB AUTO_INCREMENT=649 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `profissionais`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `profissionais` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `usuario_id` bigint unsigned DEFAULT NULL,
  `nome` varchar(120) NOT NULL,
  `registro_profissional` varchar(80) DEFAULT NULL,
  `cargo` varchar(100) NOT NULL,
  `telefone` varchar(30) DEFAULT NULL,
  `status` varchar(20) NOT NULL DEFAULT 'ATIVO',
  `criado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `atualizado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_profissionais_usuario` (`usuario_id`),
  UNIQUE KEY `uq_profissionais_registro` (`registro_profissional`),
  KEY `idx_profissionais_nome` (`nome`),
  KEY `idx_profissionais_status` (`status`),
  CONSTRAINT `fk_profissionais_usuario` FOREIGN KEY (`usuario_id`) REFERENCES `usuarios` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_profissionais_status` CHECK ((`status` in (_utf8mb4'ATIVO',_utf8mb4'INATIVO')))
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `regras_alerta`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `regras_alerta` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `codigo` varchar(60) NOT NULL,
  `descricao` varchar(255) NOT NULL,
  `dias_antecedencia` smallint unsigned NOT NULL DEFAULT '0',
  `ativo` tinyint(1) NOT NULL DEFAULT '1',
  `criado_por` bigint unsigned DEFAULT NULL,
  `criado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_regras_alerta_codigo` (`codigo`),
  KEY `fk_regras_alerta_criador` (`criado_por`),
  KEY `idx_regras_alerta_ativo` (`ativo`),
  CONSTRAINT `fk_regras_alerta_criador` FOREIGN KEY (`criado_por`) REFERENCES `usuarios` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reservas`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `reservas` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `bolsa_id` bigint unsigned NOT NULL,
  `referencia` varchar(100) DEFAULT NULL,
  `status` varchar(20) NOT NULL DEFAULT 'ATIVA',
  `reservada_por` bigint unsigned NOT NULL,
  `reservada_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `expira_em` datetime DEFAULT NULL,
  `liberada_em` datetime DEFAULT NULL,
  `motivo` text,
  `reserva_ativa_bolsa_id` bigint unsigned GENERATED ALWAYS AS ((case when (`status` = _utf8mb4'ATIVA') then `bolsa_id` else NULL end)) STORED,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_reserva_ativa_por_bolsa` (`reserva_ativa_bolsa_id`),
  KEY `fk_reservas_usuario` (`reservada_por`),
  KEY `idx_reservas_status_expira` (`status`,`expira_em`),
  KEY `idx_reservas_bolsa_status` (`bolsa_id`,`status`),
  CONSTRAINT `fk_reservas_bolsa` FOREIGN KEY (`bolsa_id`) REFERENCES `bolsas` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_reservas_usuario` FOREIGN KEY (`reservada_por`) REFERENCES `usuarios` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_reservas_status` CHECK ((`status` in (_utf8mb4'ATIVA',_utf8mb4'LIBERADA',_utf8mb4'CANCELADA',_utf8mb4'EXPIRADA',_utf8mb4'CONCLUIDA')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `sessoes`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `sessoes` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `usuario_id` bigint unsigned NOT NULL,
  `token_hash` char(64) NOT NULL,
  `criada_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `expira_em` datetime NOT NULL,
  `revogada_em` datetime DEFAULT NULL,
  `ip_origem` varchar(45) DEFAULT NULL,
  `agente_usuario` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_sessoes_token_hash` (`token_hash`),
  KEY `idx_sessoes_usuario_expira` (`usuario_id`,`expira_em`),
  KEY `idx_sessoes_expira_revogada` (`expira_em`,`revogada_em`),
  CONSTRAINT `fk_sessoes_usuario` FOREIGN KEY (`usuario_id`) REFERENCES `usuarios` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tipos_sanguineos`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `tipos_sanguineos` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `codigo` varchar(3) NOT NULL,
  `ativo` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_tipos_sanguineos_codigo` (`codigo`),
  CONSTRAINT `chk_tipos_sanguineos_codigo` CHECK ((`codigo` in (_utf8mb4'A+',_utf8mb4'A-',_utf8mb4'B+',_utf8mb4'B-',_utf8mb4'AB+',_utf8mb4'AB-',_utf8mb4'O+',_utf8mb4'O-')))
) ENGINE=InnoDB AUTO_INCREMENT=155 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `usuario_perfis`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `usuario_perfis` (
  `usuario_id` bigint unsigned NOT NULL,
  `perfil_id` bigint unsigned NOT NULL,
  `atribuido_por` bigint unsigned DEFAULT NULL,
  `atribuido_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`usuario_id`,`perfil_id`),
  KEY `fk_usuario_perfis_atribuidor` (`atribuido_por`),
  KEY `idx_usuario_perfis_perfil` (`perfil_id`),
  CONSTRAINT `fk_usuario_perfis_atribuidor` FOREIGN KEY (`atribuido_por`) REFERENCES `usuarios` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT,
  CONSTRAINT `fk_usuario_perfis_perfil` FOREIGN KEY (`perfil_id`) REFERENCES `perfis` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_usuario_perfis_usuario` FOREIGN KEY (`usuario_id`) REFERENCES `usuarios` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `usuarios`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `usuarios` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `nome` varchar(120) NOT NULL,
  `email` varchar(254) NOT NULL,
  `senha_hash` varchar(255) NOT NULL,
  `status` varchar(20) NOT NULL DEFAULT 'ATIVO',
  `tentativas_falhas` smallint unsigned NOT NULL DEFAULT '0',
  `bloqueado_ate` datetime DEFAULT NULL,
  `ultimo_login` datetime DEFAULT NULL,
  `criado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `atualizado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_usuarios_email` (`email`),
  KEY `idx_usuarios_status_nome` (`status`,`nome`),
  CONSTRAINT `chk_usuarios_status` CHECK ((`status` in (_utf8mb4'ATIVO',_utf8mb4'INATIVO',_utf8mb4'BLOQUEADO'))),
  CONSTRAINT `chk_usuarios_tentativas` CHECK ((`tentativas_falhas` >= 0))
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping events for database 'hemoflow'
--

--
-- Dumping routines for database 'hemoflow'
--
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

