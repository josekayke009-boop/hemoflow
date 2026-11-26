# HemoFlow

**Doe. Volte. Salve vidas.**

Projeto de **José Kaike Gomes dos Santos** e **João Manoel da Silva Oliveira**, feito em dupla para a disciplina Projeto Inovadores do curso de Análise e Desenvolvimento de Sistemas (4º período, Turma C, noite) da UNINASSAU Caruaru.

O HemoFlow liga doadores de sangue aos hemocentros privados. O doador vê no celular se o tipo dele está em falta, agenda a doação e acompanha os próprios direitos e benefícios. O hemocentro informa o estoque, convoca doadores compatíveis e recebe os agendamentos na hora. Parceiros (comércios, cursinhos, pré-Enem e faculdades) oferecem vantagens a quem doa, e a nossa equipe administra tudo. O piloto é em Pernambuco, mas o sistema foi pensado para o Brasil inteiro.

- **Sistema no ar:** https://hemoflow-production.up.railway.app
- **Documentação completa:** [pasta docs](docs/README.md)

<img src="docs/qrcode/qrcode-hemoflow.png" alt="QR Code para abrir o HemoFlow no celular" width="170">

Aponte a câmera do celular para abrir o HemoFlow. Para instalar como aplicativo: no Android (Chrome), abra o menu e toque em Instalar aplicativo; no iPhone (Safari), toque em Compartilhar e depois em Adicionar à Tela de Início.

## O que cada pessoa faz no sistema

| Quem | O que faz |
|---|---|
| Doador (app no celular) | vê o termômetro do estoque, recebe convocações, agenda com um código de 6 dígitos, acompanha o histórico, os direitos (como a isenção em concursos de PE), os níveis e os cupons de parceiros. Pode doar em grupo e ajustar letra, contraste e tema |
| Hemocentro privado (painel web) | acompanha o estoque por tipo, com previsão de quando cada tipo acaba, convoca doadores com a quantidade sugerida pelo sistema, gerencia a agenda e confirma cada doação pelo código |
| Parceiro (painel web) | valida cupons, cadastra ofertas, ativa ofertas de emergência e, se for cursinho ou faculdade, confere as declarações de doação dos alunos |
| Administração (nossa equipe) | cadastra hemocentros, parceiros e contas, aprova ofertas e pode "entrar como" outro perfil para dar suporte, sempre com registro na auditoria |

A primeira versão controlava bolsas dentro de um hemocentro. Depois da avaliação do projeto, mudamos o foco para captar doadores e fazer com que voltem a doar. A concepção da versão 2.0 e a proposta do novo front-end são do João Manoel.

### Versão 2.1

- **Hemocentro:** estoque em barras coloridas, previsão como "O− acaba em cerca de 4 dias", alerta automático quando um tipo entra no nível crítico e encaixe automático (quando alguém cancela, até 3 convocados recebem a vaga).
- **Doador:** contagem para a próxima doação, níveis com medalhas, card "Eu doei sangue" para compartilhar e o aviso "Doações como a sua salvam vidas".
- **Parceiro:** painel de impacto, selo com QR Code para a vitrine, oferta de emergência por 7 dias e declarações de doação para alunos.
- **Todos:** consulta sem internet. Confirmações de doação feitas offline entram numa fila e são enviadas quando a conexão volta.

As regras de doação (intervalo de 60 dias para homens e 90 para mulheres, limite anual, idade, compatibilidade) ficam em `regras.py` e têm testes. O app faz uma pré-checagem, mas quem dá a palavra final é a triagem do hemocentro.

### Assistente HemoFlow (agente de IA com RAG)

O assistente tira dúvidas de doadores e parceiros usando só a base de conhecimento do projeto e, para o doador, os dados do próprio cadastro, apenas para leitura. Fica no botão 💬 do app do doador e no item Assistente do painel do parceiro, e funciona no site publicado. Explicamos como ele foi feito em [docs/assistente-rag.md](docs/assistente-rag.md), e o guia para rodar está em [assistente/README.md](assistente/README.md).

## LGPD e documentos jurídicos

- Os [Termos de Uso](static/termos.html) e a [Política de Privacidade](static/privacidade.html) estão publicados no site, com links no login, no cadastro e no perfil do doador.
- O cadastro pede três autorizações separadas: aceite dos documentos, consentimento específico para dados de saúde (art. 11, I, da LGPD) e convocações, que é opcional e vem desmarcada.
- O doador pode excluir a própria conta pelo app. Os dados pessoais são apagados na hora e o histórico de doações fica só como número, sem identificar a pessoa.
- O aceite fica registrado na auditoria com a versão dos documentos, a data, a hora e o IP.
- Os textos seguem a LGPD, o Marco Civil da Internet, a Lei 10.205/2001 (doação de sangue) e o CDC. Antes de um uso comercial, precisam da revisão de um advogado.

## Tecnologias

- **Back-end:** Python 3 com o `http.server` da biblioteca padrão (`servidor.py`, `rotas_v2.py`, `regras.py`).
- **Banco de dados:** MySQL 8.
- **Front-end:** HTML, CSS e JavaScript em módulos, sem frameworks, instalável como aplicativo (PWA).
- **Hospedagem:** Railway, com Docker e publicação automática a cada envio ao GitHub.
- **E-mail:** Brevo na nuvem e Gmail no computador.
- **Assistente de IA:** busca semântica no FAQ e modelo `gpt-4o-mini` da OpenAI.

## Estrutura do projeto

| Pasta ou arquivo | Conteúdo |
|---|---|
| `servidor.py` | login, sessões, segurança, e-mail e arquivos das telas |
| `rotas_v2.py` | rotas do doador, do hemocentro, do parceiro, da administração, dos avisos e do assistente |
| `regras.py` | regras de negócio |
| `dados_demo.py` | dados fictícios de demonstração |
| `static/` | telas: `index.html`, estilos em `css/` e módulos em `js/` |
| `assistente/` | agente de IA com RAG |
| `banco/` | SQL de instalação e migrações |
| `scripts/` | backup, migrações, criação do administrador e modo de desenvolvimento |
| `tests/` | testes automatizados |
| `docs/` | documentação |

## Como rodar no computador

Precisa de Python 3.10 ou mais novo e MySQL 8 com o banco `hemoflow` criado.

```powershell
pip install -r requirements.txt
python scripts/migracao_005_v2.py
python scripts/migracao_006_v21.py
python scripts/dev.py
```

As duas migrações rodam uma vez só, depois de um backup (`scripts/auditar_e_backup_banco.ps1`). O `dev.py` pede a senha do root do MySQL e reinicia o servidor sozinho a cada alteração. Depois é só abrir http://127.0.0.1:8000.

Para criar dados de demonstração, todos fictícios e com e-mails `@exemplo.com`:

```powershell
curl -X POST http://127.0.0.1:8000/api/dev/semear -d "{}"
```

As contas de demonstração no computador são `admin@`, `captacao1@`, `captacao2@`, `padaria@`, `cursinho@` e `doador@exemplo.com`, com a senha `SENHA_DEMO` do arquivo `dados_demo.py`. Essa senha não vale na nuvem: lá não existe administrador de demonstração, e o administrador real vê cada perfil pelo botão "Entrar como".

## Testes

```powershell
python -m unittest tests.test_regras tests.test_seguranca tests.test_recuperacao tests.test_email -v
```

São 47 testes que não precisam de banco: regras de negócio, segurança, recuperação de senha e e-mail. Os 14 testes de ponta a ponta rodam contra o servidor local com os dados de demonstração:

```powershell
$env:HEMOFLOW_TESTE_URL="http://127.0.0.1:8000"; python -m unittest tests.test_v2_fluxos -v
```

O assistente de IA tem o seu próprio roteiro de 15 perguntas, descrito em [docs/assistente-rag.md](docs/assistente-rag.md).

## Documentação

O índice está em [docs/README.md](docs/README.md). Os principais documentos são:

- [Documentação completa 2.1, em PDF](docs/documentacao/HemoFlow%20-%20Documentacao%202.1.pdf) (também em Word, na mesma pasta);
- [Assistente de IA com RAG](docs/assistente-rag.md);
- [Arquitetura](docs/arquitetura.md), [Banco de dados](docs/banco-de-dados.md) e [Implantação](docs/implantacao.md).

## Autoria

- **José Kaike Gomes dos Santos:** back-end e banco de dados.
- **João Manoel da Silva Oliveira:** concepção da versão 2.0, proposta do novo front-end, testes e banco de dados.

Análise e Desenvolvimento de Sistemas, UNINASSAU Caruaru, 2026. Desenvolvido com apoio de ferramentas de IA para revisão e testes.
