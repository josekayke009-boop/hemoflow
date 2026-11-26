# Implantação do HemoFlow

**Autores:** José Kaike Gomes dos Santos e João Manoel da Silva Oliveira

O sistema está publicado no Railway, no plano de teste: https://hemoflow-production.up.railway.app

## 1. Como está montado

O projeto `cheerful-fascination` no Railway tem dois serviços:

- **hemoflow:** a aplicação, montada pelo `Dockerfile` (Python 3.12, usuário sem privilégio de root, porta 8080);
- **MySQL:** o banco, ligado à aplicação pela rede privada, com TLS.

A cada envio para a branch `main` do GitHub, o Railway monta a imagem de novo e só coloca a versão nova no ar quando `/healthz` responde. A branch `v2` é onde trabalhamos; a `main` é a que vai para a nuvem.

## 2. Variáveis do serviço hemoflow

| Variável | Uso |
|---|---|
| `HEMOFLOW_ENV` | `production`: cookie `Secure`, HSTS e escuta em `0.0.0.0` |
| `HEMOFLOW_PUBLIC_URL` | endereço do site, usado nos links dos e-mails |
| `HEMOFLOW_DB_HOST`, `_PORT`, `_NAME`, `_USER`, `_PASSWORD` | conexão com o serviço MySQL |
| `HEMOFLOW_DB_SSL`, `HEMOFLOW_DB_POOL_SIZE` | TLS obrigatório e tamanho do pool de conexões |
| `HEMOFLOW_TZ` | `America/Recife`, para datas e prazos no horário local |
| `HEMOFLOW_TRUST_PROXY` | usa o IP real da pessoa no limite de tentativas de login |
| `HEMOFLOW_AUTO_INSTALL` | cria as tabelas se o banco estiver vazio |
| `HEMOFLOW_BREVO_API_KEY` | envio de e-mail pelo Brevo. Na nuvem é obrigatório, porque o plano de teste bloqueia as portas de e-mail (SMTP) |
| `HEMOFLOW_EMAIL_USER`, `HEMOFLOW_EMAIL_PASSWORD` | conta de e-mail usada como remetente |
| `OPENAI_API_KEY` | liga o assistente de IA na nuvem |
| `HEMOFLOW_ASSISTENTE_LIMITE_DIA` | opcional: limite de perguntas por dia ao assistente (padrão 100) |
| `HEMOFLOW_DEMO_SENHA` | opcional: senha das contas fictícias de demonstração |
| `HEMOFLOW_EMAIL_CONVOCACAO` | opcional: `1` para mandar e-mail também nas convocações |

As senhas e chaves ficam só no Railway. Nada disso vai para o GitHub.

## 3. Primeira instalação

1. Com `HEMOFLOW_AUTO_INSTALL=1`, o servidor roda os arquivos de `banco/instalacao/` na primeira vez que encontra o banco vazio. Entram só perfis, tipos sanguíneos, benefícios e locais públicos, sem nenhum dado pessoal.
2. O administrador é criado no Console do serviço hemoflow com `python scripts/criar_administrador.py`. A senha é digitada pela própria pessoa.
3. Para conferir, `https://hemoflow-production.up.railway.app/healthz` deve responder `{"ok": true, "banco": "ok"}`.
4. Para ter dados de demonstração, rode `python dados_demo.py` no Console. São criados hemocentros, parceiros e doadores fictícios, com e-mails `@exemplo.com`. Na nuvem não é criado administrador de demonstração; o administrador real vê cada perfil pelo botão "Entrar como".

## 4. Computador e nuvem

| | Computador | Nuvem |
|---|---|---|
| Iniciar | `python scripts/dev.py` | automático a cada envio para a `main` |
| Endereço | http://127.0.0.1:8000 | https://hemoflow-production.up.railway.app |
| Banco | MySQL do computador | MySQL do Railway |
| E-mail | Gmail | Brevo |
| Assistente de IA | `assistente/servico.py`, com embeddings locais | dentro do servidor, com embeddings da OpenAI |

## 5. Como atualizamos o sistema

1. Alteramos e testamos no computador:
   ```powershell
   python -m unittest tests.test_regras tests.test_seguranca tests.test_recuperacao tests.test_email -v
   ```
2. Fazemos o commit na `v2` e levamos para a `main`. O Railway publica em 1 ou 2 minutos.
3. Se mudou algo em `static/`, aumentamos o `VERSION` em `static/sw.js` para o app instalado baixar a versão nova.
4. Se a mudança mexe na estrutura do banco, fazemos o backup antes e depois rodamos a migração no Console, por exemplo `python scripts/migracao_006_v21.py --usar-variaveis`.

## 6. Backup

- **Banco do computador:** `scripts/auditar_e_backup_banco.ps1`.
- **Banco da nuvem:** no Console do serviço hemoflow, `python scripts/backup_interno.py --usar-variaveis`. Ele copia cada tabela para outra com o prefixo `bkp_` e a data, dentro do próprio banco, já que o plano de teste não faz backup automático.
- Os arquivos de backup nunca vão para o GitHub.

## 7. Limitações

- O plano de teste do Railway tem prazo. Quando acabar, os serviços param e será preciso um plano pago ou outra hospedagem.
- As sessões ficam na memória do servidor, então cada publicação nova desconecta quem estava logado.
