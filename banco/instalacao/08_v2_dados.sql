-- HemoFlow 2.0 — dados de referência da migração 005 (pode rodar mais de uma vez).

-- Benefícios do doador. uf NULL = vale no Brasil todo.
INSERT INTO beneficios_estado (uf, titulo, descricao, minimo_homens, minimo_mulheres, janela_meses)
SELECT NULL, '1 dia de folga no trabalho', 'A CLT garante 1 dia de folga, a cada 12 meses de trabalho, no dia da doação voluntária de sangue devidamente comprovada.', NULL, NULL, 12
WHERE NOT EXISTS (SELECT 1 FROM beneficios_estado WHERE uf IS NULL AND titulo = '1 dia de folga no trabalho');

INSERT INTO beneficios_estado (uf, titulo, descricao, minimo_homens, minimo_mulheres, janela_meses)
SELECT 'PE', 'Isenção de taxa em concursos estaduais', 'Doador regular: mínimo de 3 doações (homens) ou 2 (mulheres) nos 12 meses anteriores ao edital. Comprovação pela declaração da entidade coletora.', 3, 2, 12
WHERE NOT EXISTS (SELECT 1 FROM beneficios_estado WHERE uf = 'PE' AND titulo = 'Isenção de taxa em concursos estaduais');

-- Locais públicos de doação (aparecem em "Onde doar", sem estoque e sem convocação).
INSERT INTO unidades (banco_id, nome, tipo, endereco, bairro, cidade, uf, horario)
SELECT NULL, 'HEMOPE · Recife (sede)', 'PUBLICO', 'Rua Joaquim Nabuco, 171', 'Graças', 'Recife', 'PE', 'Consulte os horários no site do HEMOPE'
WHERE NOT EXISTS (SELECT 1 FROM unidades WHERE nome = 'HEMOPE · Recife (sede)');

INSERT INTO unidades (banco_id, nome, tipo, endereco, bairro, cidade, uf, horario)
SELECT NULL, 'HEMOPE · Hemocentro de Caruaru', 'PUBLICO', NULL, NULL, 'Caruaru', 'PE', 'Consulte endereço e horários no site do HEMOPE'
WHERE NOT EXISTS (SELECT 1 FROM unidades WHERE nome = 'HEMOPE · Hemocentro de Caruaru');
