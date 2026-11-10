# Roteiro sugerido para apresentação do TCC

## 1. Contexto e problema

Explique o problema de organização e consulta de um estoque de bolsas como cenário acadêmico. Evite afirmar que o protótipo resolve problemas clínicos reais ou que substitui controles existentes.

## 2. Objetivo

Apresentar uma aplicação web local que permite registrar unidades, consultar disponibilidade operacional por tipo, identificar datas próximas de validade e acompanhar mudanças de situação.

## 3. Tecnologias e arquitetura

- Interface web responsiva: HTML, CSS e JavaScript.
- API HTTP/JSON e regras da aplicação: Python padrão.
- Persistência local: SQLite.
- Execução: aplicação local em `127.0.0.1`.

Mostre o diagrama em `arquitetura.md` e o modelo de dados em `banco-de-dados.md`.

## 4. Demonstração sugerida

1. Executar `python3 app.py` e abrir `http://127.0.0.1:8000`.
2. Cadastrar bolsas com dados fictícios e anonimizados de diferentes tipos.
3. Conferir cartões, contagem por grupo e tabela.
4. Filtrar por tipo/status e pesquisar por código/local.
5. Mudar o status de uma bolsa e mostrar o histórico.
6. Explicar como validade e tentativas de transição inválidas são tratadas.
7. Executar os testes automatizados e mostrar a documentação.

Use datas de validade futuras para a demonstração. Não use registros clínicos ou dados pessoais reais.

## 5. Limitações e evolução

Discuta ausência de autenticação e implantação segura, necessidade de revisão das regras por especialistas, backups, permissões, testes mais abrangentes, segurança, requisitos legais, interoperabilidade e governança de dados antes de qualquer uso fora do ambiente acadêmico.

## 6. Perguntas que vale preparar

- Por que SQLite atende à demonstração e em que cenário seria necessário outro banco?
- Como as validações no servidor protegem as regras além das verificações visuais?
- Como os índices ajudam nas consultas por tipo, status e validade?
- Que riscos existem em publicar dados de estoque e como preveni-los?
- O que precisaria mudar para autenticação, múltiplos usuários e auditoria confiável?
- Por que o indicador de tipo sanguíneo não equivale a uma recomendação de transfusão?
