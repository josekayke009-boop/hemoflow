# HemoFlow

**Doe. Volte. Salve vidas.**

Plataforma que liga doadores de sangue aos bancos de sangue privados. O doador vê no celular onde o tipo dele está em falta, agenda a doação e acompanha os próprios direitos e benefícios. O banco de sangue informa o estoque, convoca doadores compatíveis e recebe os agendamentos na hora. Parceiros (comércios, cursinhos, pré-Enem e faculdades) oferecem vantagens a quem doa. A equipe HemoFlow administra tudo.

Começa com um piloto em Pernambuco e foi pensada para o Brasil inteiro.

Projeto da disciplina **Projeto Inovadores** — Análise e Desenvolvimento de Sistemas (4º período, Turma C, noite), UNINASSAU Caruaru.

- **Sistema no ar:** https://hemoflow-production.up.railway.app
- **Código:** https://github.com/josekayke009-boop/hemoflow

<img src="docs/qrcode/qrcode-hemoflow.png" alt="QR Code para abrir o HemoFlow no celular" width="170">

Aponte a câmera do celular para abrir o HemoFlow. Para instalar como aplicativo: no Android (Chrome), menu → **Instalar aplicativo**; no iPhone (Safari), Compartilhar → **Adicionar à Tela de Início**.

## Versão 2.0

A versão 1 controlava bolsas dentro de um hemocentro. A 2.0 muda o foco para **captar e trazer de volta doadores**:

| Quem | O que faz no HemoFlow |
|---|---|
| **Doador** (app de celular) | Termômetro do estoque do seu tipo e dos 8 tipos; convocações; agendamento com código de 6 dígitos; cancelamento; histórico; direitos por estado (ex.: isenção em concursos de PE) e conquistas; grupos de doação; cupons de parceiros; ajuda; letra maior, alto contraste, tema escuro e menos animações |
| **Banco de sangue privado** (painel web) | Estoque por tipo com termômetro e limites próprios; convocação com quantidade sugerida pelo sistema; agenda e abertura de horários; aviso a cada agendamento/cancelamento; confirmação da doação pelo código; marcação de falta; resultados (comparecimento e retorno); ajuda |
| **Parceiro** (painel web) | Validação de cupom (uso único); cadastro de ofertas (aprovadas pela equipe); para cursinhos e faculdades, código dos alunos e relatório só com números gerais |
| **Admin — equipe HemoFlow** | Acesso total: bancos, unidades, hemocentros públicos, parceiros, ofertas, doadores e contas; “entrar como” banco, parceiro ou doador; tudo registrado na auditoria |

Regras principais (em `regras.py`, com testes): intervalo de 60 dias (homens) e 90 dias (mulheres), limite de 4 e 3 doações por ano, idade de 16 a 69 anos com autorização do responsável para 16 e 17, compatibilidade sanguínea, níveis do termômetro e cálculo de quantos doadores convocar (considerando que cerca de metade comparece). Cupons exigem doação verificada nos últimos 6 meses. O app faz uma pré-checagem e a triagem do banco de sangue dá a palavra final.

**Concepção da versão 2.0 e proposta do novo front-end: João Manoel da Silva Oliveira.**

## Tecnologias

- **Backend:** Python 3 (biblioteca padrão `http.server`): `servidor.py`, `rotas_v2.py`, `regras.py`
- **Banco de dados:** MySQL 8 (`mysql-connector-python`)
- **Frontend:** HTML, CSS e JavaScript (módulos), sem frameworks, na pasta `static/`. É um aplicativo instalável (PWA)
- **Hospedagem:** Railway (contêiner Docker + MySQL), publicação automática a cada envio ao GitHub
- **E-mail:** Brevo (nuvem) ou Gmail (computador), para recuperação de senha, código de login e suporte

## Estrutura do projeto

```
hemoflow/
├── servidor.py              Servidor: login, sessões, segurança, e-mail, arquivos das telas
├── rotas_v2.py              Rotas da versão 2.0 (doador, banco de sangue, parceiro, admin, avisos)
├── regras.py                Regras de negócio (aptidão, compatibilidade, termômetro, convocação, metas)
├── dados_demo.py            Dados FICTÍCIOS de demonstração
├── static/
│   ├── index.html           Página única (login 3D, cadastro, recuperação de senha)
│   ├── css/app.css          Visual (claro/escuro, acessibilidade)  ·  css/login-3d.css  fundo animado do login
│   ├── js/app.js            Entrada e escolha da área pelo perfil
│   ├── js/nucleo.js         Peças comuns (API, avisos, janela, termômetro, preferências, ícones)
│   ├── js/doador.js         App do doador
│   ├── js/painel.js         Molde dos painéis web
│   ├── js/banco.js · parceiro.js · admin.js   Painéis
│   ├── js/ajuda.js          Aba Ajuda de todos os perfis
│   └── manifest.webmanifest e sw.js   Aplicativo instalável
├── banco/instalacao/        SQL para criar o banco do zero (inclui a versão 2.0: arquivos 07 e 08)
├── banco/migracoes/         Alterações de estrutura, cada uma com o script para desfazer
├── scripts/                 Backup, migrações, administrador, modo desenvolvimento (dev.py)
├── tests/                   Testes automatizados
└── docs/                    Documentação (v2/plano-tecnico.md, arquitetura, banco, implantação...)
```

## Como executar no computador

Pré-requisitos: Python 3.10 ou superior e MySQL 8 com o banco `hemoflow` criado.

```powershell
pip install -r requirements.txt
python scripts/migracao_005_v2.py        # uma vez, depois de um backup (scripts/auditar_e_backup_banco.ps1)
python scripts/dev.py                     # pede a senha do root do MySQL e reinicia sozinho a cada mudança
```

Abra http://127.0.0.1:8000. Para ter dados de demonstração (todos fictícios, e-mails `@exemplo.com`):

```powershell
curl -X POST http://127.0.0.1:8000/api/dev/semear -d "{}"
```

Contas de demonstração no computador: `admin@`, `captacao1@`, `captacao2@`, `padaria@`, `cursinho@` e `doador@exemplo.com`, com a senha `SENHA_DEMO` de `dados_demo.py`. **Na nuvem** essa senha não vale: lá as contas demo usam a variável `HEMOFLOW_DEMO_SENHA` do Railway e não existe admin de demonstração.

## Testes

```powershell
python -m unittest tests.test_regras tests.test_seguranca tests.test_recuperacao tests.test_email -v
```

São 44 testes que não precisam de banco (regras de negócio, segurança, recuperação de senha e e-mail). Há também os testes de ponta a ponta da 2.0, que rodam contra o servidor local com os dados de demonstração:

```powershell
$env:HEMOFLOW_TESTE_URL="http://127.0.0.1:8000"; python -m unittest tests.test_v2_fluxos -v
```

## Documentação

- [Plano técnico da versão 2.0](docs/v2/plano-tecnico.md): perfis, tabelas, regras e etapas
- [Arquitetura](docs/arquitetura.md): como as partes se comunicam
- [Banco de dados](docs/banco-de-dados.md): tabelas e relacionamentos
- [Implantação](docs/implantacao.md): nuvem, variáveis, atualização e backup
- [Relatório de testes](docs/relatorio-testes.md)
- [Relatório de auditoria](docs/relatorio-auditoria.md)
- [Roteiro de apresentação](docs/roteiro-apresentacao.md)

## Autoria

- **José Kaike Gomes dos Santos**: back-end e banco de dados
- **João Manoel da Silva Oliveira**: concepção da versão 2.0, proposta do novo front-end, testes e banco de dados

Análise e Desenvolvimento de Sistemas, UNINASSAU Caruaru. Desenvolvido com apoio de ferramentas de IA para revisão e testes.
