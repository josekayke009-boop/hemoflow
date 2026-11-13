# Auditoria técnica do HemoFlow (10/11/2026)

> **Nota:** este relatório foi escrito antes da reorganização das pastas e cita os nomes de arquivo da época. Correspondência atual: `app_mysql.py` → `servidor.py`; `setup_admin.py` → `scripts/criar_administrador.py`; `migrar_cadastros.py` → `scripts/migracao_000_tipo_sanguineo_peso.py`; `sql/` → `banco/`; `static/app.js` → `static/js/app.js`; `static/styles.css` → `static/css/estilos.css`; `tests/test_cadastros_mysql.py` → `tests/test_cadastros.py`; `tests/test_producao.py` → `tests/test_seguranca.py`. Os resultados registrados não foram alterados.

Etapa 1 do plano de finalização e migração. Nenhum arquivo de código ou do banco foi alterado nesta etapa.

## 1. O que foi verificado

| Item | Como | Resultado |
|---|---|---|
| Estrutura de arquivos | listagem completa da pasta | 42 arquivos (ver seção 2) |
| Backend em uso | leitura de `app_mysql.py` (1.103 linhas) | todas as rotas mapeadas (seção 3) |
| Frontend | leitura de `static/index.html` e `static/app.js` | todas as chamadas `fetch` conferidas com o backend |
| Testes existentes | `python -m unittest discover -s tests -v` | **5/5 aprovados**, porém testam só o `app.py` (SQLite) |
| Compilação | `py_compile` em `app_mysql.py`, `setup_admin.py`, `migrar_cadastros.py` | sem erros |
| Senhas no código | busca por `senha=`/`password=` literais | nenhuma senha fixa encontrada |
| MySQL | serviço `MySQL80` | **em execução**, início automático; MySQL Server 8.0 + Workbench instalados |
| Ambiente | Python 3.14.0, mysql-connector 26.10.0 | ok |
| Git | `git status` | repositório criado, **nenhum commit ainda** |
| Banco (tabelas, dados, FKs) | **não foi possível** — exige a senha do MySQL | ver seção 6 |

## 2. Estrutura real do projeto

```
HemoFlow/
├── app_mysql.py          ← BACKEND EM USO (MySQL, sessão, perfis) — iniciado por iniciar_hemoflow.ps1
├── app.py                ← versão antiga SQLite (legado); só ela é coberta pelos testes
├── hemoflow.db           ← banco SQLite antigo (22/10), não usado pelo app MySQL
├── setup_admin.py        ← cria o 1º administrador (pede senhas sem exibir)
├── migrar_cadastros.py   ← adiciona doadores.tipo_sanguineo / peso_kg
├── iniciar_hemoflow.ps1  ← inicia o app MySQL
├── sql/criar_recuperacao_senhas.sql  ← única DDL versionada
├── static/ index.html, app.js, styles.css, hemoflow-logo.png (1,9 MB)
├── tests/test_app.py     ← testa app.py (SQLite)
├── docs/                 ← arquitetura e banco descrevem a versão SQLite (desatualizados)
└── _backup_auditoria_20261109_005554/  ← backup anterior (app_mysql, static, setup_admin)
```

**Ausentes:** `requirements.txt`, `.env.example`, script de criação completa do banco MySQL (estrutura das ~15 tabelas não está versionada em lugar nenhum), testes do app MySQL, documentação de implantação.

## 3. Mapa frontend ↔ backend

| Chamada do `app.js` | Rota em `app_mysql.py` | Proteção | Situação |
|---|---|---|---|
| GET `/api/session` | existe | pública | ok |
| POST `/api/login`, `/api/logout` | existem | pública, limite 10 tentativas/15 min por IP | ok |
| POST `/api/forgot-password`, `/api/reset-password` | existem | pública | depende de SMTP + tabela `recuperacao_senhas` |
| GET `/api/summary` | existe | `painel.consultar` | ok |
| GET/POST `/api/bags` | existem | `estoque.consultar` / `estoque.bolsa.criar` | ok |
| POST `/api/bags/{id}/transition` | existe | permissão por status | ok |
| GET `/api/movements` | existe | `estoque.consultar` | ok |
| GET/POST `/api/donors` | existem | `doadores.consultar` / `doadores.criar` | ok |
| POST `/api/professionals` | existe | só ADMINISTRADOR | ok |
| GET/POST `/api/access-accounts` | existem | só ADMINISTRADOR | ok |

Todas as rotas usadas pelo frontend existem no backend atual. Nenhum arquivo JS duplicado é servido: o HTML carrega um único `/app.js`, e `static/` só tem um.

## 4. Os problemas relatados

### Problema 1: e-mails duplicados

- **Doadores:** o código atual (`create_donor`) já recusa e-mail repetido. Mas a coluna `doadores.email` **não tem UNIQUE no MySQL**, e a busca usa `LOWER(email)=...`, o que impede o uso do índice. Com dois cadastros simultâneos, o bloqueio `FOR UPDATE` em intervalo vazio pode gerar *deadlock* (erro 500), em vez de uma mensagem clara. **Correção:** migração reversível com índice UNIQUE em `doadores(email)`, *depois* de conferir se já existem duplicados no banco (o script de auditoria conta isso).
- **Profissionais:** a tabela `profissionais` **não tem coluna de e-mail**. O formulário pede e-mail e data de nascimento como obrigatórios e depois **descarta os dois** sem avisar. Por isso não existe como bloquear duplicidade: o dado nem é salvo. **Correção proposta:** migração que adiciona `profissionais.email` com UNIQUE, mais validação no backend e mensagem 409. A alternativa é exigir que todo profissional tenha uma conta em `usuarios`, que já tem `uq_usuarios_email`. Essa escolha é sua (seção 8).
- **Contas de acesso:** já protegidas por `uq_usuarios_email` + verificação prévia + tradução do erro 1062 para 409.

### Problema 2: "Carregando perfis..."

- O `<select>` começa com "Carregando perfis..." e só é preenchido quando GET `/api/access-accounts` responde. Se a rota responde 404/403/500, o texto muda para "Não foi possível carregar os perfis".
- O backup de 09/11 mostra que a rota e o tratamento de erro foram acrescentados recentemente. A causa provável dos sintomas antigos é que **um servidor antigo continuava ouvindo a porta 8000** (no Windows, `SO_REUSEADDR` deixa dois processos na mesma porta) e servia o `app.js`/backend antigos. Isso explica também o `checkSession is not defined` e o 404. O código atual já desliga isso no Windows e envia `Cache-Control: no-cache`.
- **Lacuna real que continua:** o formulário de **profissional ("Pessoa licenciada") não tem campo de perfil**. Ele mostra "Equipe e acesso ao sistema", mas não cria acesso nenhum. Isso precisa ser alinhado (seção 8).
- **Ainda falta verificar no navegador com o banco ligado.** Não declaro como resolvido antes disso.

### Problema 3: comunicação frontend/backend

Hoje não há divergência estática: `checkSession` está definida (`app.js:54`) e `/api/access-accounts` existe. Isso será confirmado em teste real (Etapa 4).

### Problema 4: banco / `Access denied`

- O app lê a senha só de `HEMOFLOW_DB_PASSWORD`, que **não está salva** nas variáveis do usuário. É preciso digitá-la a cada início, e o erro aparece se ela não conferir com a conta `'hemoflow_app'@'localhost'`.
- `migrar_cadastros.py` roda com `hemoflow_app`, que **não tem CREATE** (documentado no código) e provavelmente também não tem ALTER. Esse script deve rodar com um usuário administrativo.
- A conta pode existir como `@'localhost'` e não como `@'127.0.0.1'`/`'%'`. Os dois casos são conferidos pela auditoria.

## 5. Outros achados

**Segurança**
1. O cookie de sessão não tem `Secure`. Obrigatório quando houver HTTPS (nuvem).
2. Faltam os cabeçalhos `Content-Security-Policy` e `X-Frame-Options`/`frame-ancestors`, o que deixa o sistema exposto a clickjacking.
3. O limite de login usa o IP da conexão. Atrás do proxy da hospedagem, **todos os usuários teriam o mesmo IP**: 10 erros de qualquer pessoa bloqueiam todo mundo. Também falta bloqueio por conta (a coluna `tentativas_falhas` existe e não é usada).
4. `forgot-password` responde 502 apenas quando o e-mail existe e o SMTP falha, o que deixa perceber quais e-mails estão cadastrados.
5. O link de recuperação usa `http://{HOST}:{PORT}`. Na nuvem isso viraria `http://0.0.0.0:...`. É preciso uma variável `HEMOFLOW_PUBLIC_URL`.
6. As sessões ficam em memória: um reinício ou nova implantação desconecta todo mundo, e não funciona com mais de uma instância. Para um projeto acadêmico, uma instância é suficiente; vale documentar.
7. Pontos positivos: SQL 100% parametrizado (nenhuma concatenação de entrada do usuário); hash PBKDF2-SHA256 com sal; autorização checada **no servidor** em todas as rotas; `esc()` aplicado nos dados exibidos (XSS); erros internos não vazam detalhes; proteção contra *path traversal* nos estáticos.

**Banco / desempenho na nuvem**
8. Cada requisição abre de 2 a 4 conexões novas com o MySQL (`is_admin_profile` + `require_permission` + consulta). Com banco remoto e TLS, cada tela fica lenta. **Correção:** pool de conexões.
9. A conexão não tem opções SSL. MySQL gerenciado na nuvem exige TLS.
10. `date.today()` usa o fuso do servidor. Na nuvem (UTC), "vencidas" e "vencem em 7 dias" mudariam às 21h de Recife. É preciso fixar `TZ=America/Recife`.
11. O app escuta em `127.0.0.1:8000` por padrão. Na nuvem precisa ser `0.0.0.0` e a porta definida pela plataforma (já configurável por variável de ambiente).

**Organização**
12. `app.py` + `hemoflow.db` + `tests/test_app.py` formam um segundo sistema (SQLite) sem uso, e o README e o `docs/` ainda descrevem esse sistema. Proposta: mover para `legado/`, sem apagar.
13. `.gitignore` tem blocos duplicados. `_backup_auditoria_*` já está ignorado (ok).
14. Identidade: a tela de login e a barra lateral dizem **"Hemovita"**, enquanto o título e o resto dizem HemoFlow. `theme-color` é `#f00012` (vermelho vivo, não vinho). O logo PNG tem 1,9 MB (lento no celular).
15. `setup_admin.py` usa 600.000 iterações e `app_mysql.py` usa 310.000. Ambos são aceitos; o ideal é padronizar.

**Funcionalidades vs. o que está pedido**

| Área | Situação real |
|---|---|
| Login, sessão, logout, recuperação | integrado (recuperação depende de SMTP) |
| Doadores | cadastro + listagem; **sem editar/inativar** |
| Contas de acesso | criar + listar; **sem editar, inativar ou trocar perfil** |
| Perfis/permissões | matriz no banco, checada no servidor |
| Profissionais | só cadastro; **não há listagem nem edição** (nenhuma rota GET) |
| Bolsas / estoque / movimentações | integrados |
| Reservas e descartes | gravados automaticamente na transição; sem tela própria |
| Alertas | calculados no navegador (limites fixos 5/10/15); "estoque mínimo" não é configurável |
| Relatórios | só indicadores na tela; **sem exportação** (CSV/PDF) |
| Comunicação / notificações | **apenas visual** (já sinalizado na própria tela) |

## 6. Banco de dados: pendente da sua senha

Não tenho e não devo digitar a senha do MySQL. Criei um script **somente leitura** que faz o backup completo e a auditoria:

```powershell
cd C:\Users\josek\Documents\HemoFlow
.\scripts\auditar_e_backup_banco.ps1
```

Ele pede a senha do `root` sem exibi-la e gera, em `Documents\HemoFlow_backups\banco_<data>\`:
`hemoflow_completo.sql` (backup restaurável), `hemoflow_estrutura.sql` (DDL, base para a nuvem) e `auditoria.txt` (tabelas, contagens, FKs, índices, CHECKs, matriz de permissões, duplicidades, privilégios do `hemoflow_app`, **sem dados pessoais**).

## 7. Backup do código (Etapa 2, parte 1): feito

`C:\Users\josek\Documents\HemoFlow_backups\codigo_20261110_125202\` + `.zip` (42 arquivos, cópia integral antes de qualquer alteração).

## 8. Plano de execução proposto

**Etapa 3: correções (no código, sem mudar a arquitetura Python + MySQL)**
1. `sql/migracoes/001_*.sql` + `001_*_reverter.sql`: UNIQUE em `doadores.email`; `profissionais.email` UNIQUE (conforme sua decisão); executados por você com usuário administrativo, depois do backup.
2. Backend: verificação de duplicidade usando o índice, mensagem 409 clara, validação de e-mail do profissional, pool de conexões, SSL opcional por variável, `HEMOFLOW_PUBLIC_URL`, cookie `Secure` em produção, CSP/X-Frame-Options, IP real atrás de proxy confiável + bloqueio por conta.
3. Frontend: formulário de profissional coerente com o que é salvo, seleção de perfil funcional, "Hemovita" → HemoFlow, cor vinho, logo otimizado.
4. Organização: `requirements.txt`, `.env.example`, `.gitignore` limpo, `legado/` para a versão SQLite, README e `docs/banco-de-dados.md` atualizados.

**Etapa 4: testes**: suíte automatizada contra um banco MySQL **de teste** (`hemoflow_teste`, dados fictícios) cobrindo login, permissões, duplicidades, perfis, bolsas, movimentações; mais teste manual no navegador. Resultado registrado teste a teste como aprovado/reprovado.

**Etapa 5: nuvem**: comparação de custos com preços verificados no dia, `Dockerfile`/config da plataforma, variáveis de ambiente, script de importação da estrutura, rotina de backup.

**Etapas 6–8**: implantação **só após sua autorização expressa** de serviço e custo; teste de acesso externo; relatório final.

Pré-seleção de hospedagem (preços a confirmar na Etapa 5): **Railway** (app + MySQL no mesmo painel, mais simples, pago por uso após o crédito de teste); **Render/Koyeb (app) + Aiven MySQL (plano gratuito)** (custo zero possível, mas o app gratuito "dorme" e o banco gratuito é pequeno); **VPS (ex.: Oracle Cloud Always Free, Hetzner)** (mais barato e flexível, porém você administraria o servidor, o HTTPS e os backups). Para um projeto acadêmico, a tendência é Railway ou Render + Aiven.

## 9. Decisões que dependem de você

1. Profissionais: adicionar coluna `email` UNIQUE em `profissionais`, ou todo profissional passa a ser criado junto com uma conta de acesso (e perfil)?
2. Autoriza mover `app.py`, `hemoflow.db` e os testes SQLite para `legado/` (sem apagar)?
3. O nome visível deve ser **HemoFlow** em todas as telas (substituindo "Hemovita")?
4. O banco local tem só dados fictícios? (Define se o dump pode ir para a nuvem.)

## 10. Resultado da auditoria do banco (backup `banco_20261110_125916`)

- MySQL 8.0.46, utf8mb4 / `utf8mb4_0900_ai_ci` (comparação de e-mail sem diferenciar maiúsculas), modo estrito ativo.
- 27 tabelas InnoDB, todas com chaves estrangeiras coerentes.
- **Nenhum e-mail repetido** em `doadores` nem em `usuarios`, e nenhum usuário sem perfil. A migração 001 pode ser aplicada.
- 4 perfis com a matriz de permissões completa (ADMINISTRADOR 34, RESPONSAVEL_TECNICO 25, OPERADOR_ESTOQUE 13, CONSULTA 10).
- `hemoflow_app@localhost`: SELECT, INSERT, UPDATE, DELETE e **ALTER** em `hemoflow.*`. Não tem CREATE. A conta existe só para `localhost`.
- **A tabela `recuperacao_senhas` não existe**, então "Esqueceu sua senha?" responde 503 até `sql/criar_recuperacao_senhas.sql` ser executado.
- O banco já tem tabelas para recursos que o app ainda não usa: `agendamentos`, `doacoes`, `alertas`, `regras_alerta`, `limites_estoque` (estoque mínimo), `mensagens`, `notificacoes`, `execucoes_relatorios`, `configuracoes` e `sessoes`. Isso facilita implementar alertas configuráveis, relatórios e comunicação sem mudar a estrutura.
