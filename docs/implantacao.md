# Implantação do HemoFlow

O sistema está publicado no **Railway** (período de teste gratuito, sem cartão): https://hemoflow-production.up.railway.app

## 1. Como está montado

```
Navegador ──HTTPS──► Proxy do Railway (certificado automático)
                         │  HTTP interno + X-Forwarded-For
                         ▼
                   Serviço "hemoflow" (Dockerfile)
                   servidor.py: API + telas (static/)
                         │  rede privada do projeto, TLS
                         ▼
                   Serviço "MySQL" (MySQL 8)
```

- O serviço `hemoflow` está ligado ao repositório do GitHub: **cada envio para a branch `main` gera uma nova publicação automaticamente**.
- O frontend é servido pelo próprio `servidor.py`, então não existe um segundo serviço para hospedar.
- Senhas e segredos ficam **somente** nas variáveis do painel do Railway (modelo em `.env.example`). Nada disso vai para o código ou para o GitHub.

## 2. Variáveis do serviço `hemoflow`

| Variável | Valor |
|---|---|
| `HEMOFLOW_ENV` | `production` (escuta em `0.0.0.0`, cookie `Secure`, HSTS) |
| `PORT` | `8080` |
| `HEMOFLOW_PUBLIC_URL` | `https://hemoflow-production.up.railway.app` (usado no link do e-mail de recuperação) |
| `HEMOFLOW_DB_HOST`, `_PORT`, `_NAME`, `_USER`, `_PASSWORD` | referências ao serviço MySQL: `${{MySQL.MYSQLHOST}}` etc. |
| `HEMOFLOW_DB_SSL` | `required` |
| `HEMOFLOW_DB_POOL_SIZE` | `3` |
| `HEMOFLOW_TZ` | `America/Recife` (vencimentos e `NOW()` no horário local) |
| `HEMOFLOW_TRUST_PROXY` | `1` (IP real do usuário para o limite de tentativas de login) |
| `HEMOFLOW_AUTO_INSTALL` | `1` (cria as tabelas se o banco estiver vazio) |
| `HEMOFLOW_EMAIL_USER`, `HEMOFLOW_EMAIL_PASSWORD` | conta Gmail e **senha de app** de 16 letras, para a recuperação de senha |

No painel (*Settings*) também estão configurados: verificação de saúde em `/healthz` e porta de destino `8080`.

## 3. Primeira instalação

1. **Estrutura do banco:** com `HEMOFLOW_AUTO_INSTALL=1`, o `servidor.py` executa os arquivos de `banco/instalacao/` na primeira vez que encontra o banco vazio. Só entram perfis, permissões, tipos sanguíneos e hemocomponentes — **nenhum dado pessoal**.
2. **Administrador:** no Railway, abra o serviço `hemoflow` → *Console* e rode
   ```bash
   python scripts/criar_administrador.py
   ```
   O script pede nome, e-mail e senha (a senha aparece como asteriscos).
3. **Conferir:** `https://hemoflow-production.up.railway.app/healthz` deve responder `{"ok": true, "banco": "ok"}`.

Os doadores e bolsas do banco local **não** foram copiados para a nuvem.

## 4. Local x nuvem

| | Computador | Nuvem |
|---|---|---|
| Iniciar | `.\iniciar_hemoflow.ps1` | automático a cada envio ao GitHub |
| `HEMOFLOW_ENV` | `development` (padrão) | `production` |
| Endereço | http://127.0.0.1:8000 | https://hemoflow-production.up.railway.app |
| Banco | MySQL do computador | MySQL do Railway |
| Cookie `Secure` / HSTS | não | sim |

## 5. Atualizar o sistema

1. Alterar e testar no computador:
   ```powershell
   python -m unittest discover -s tests -v
   .\iniciar_hemoflow.ps1
   ```
2. `git add`, `git commit` e `git push`. O Railway reconstrói a imagem e publica sozinho (cerca de 1 a 2 minutos).
3. Se alterou arquivos de `static/`, aumente o `VERSION` em `static/sw.js` para o aplicativo instalado baixar a versão nova.
4. Mudanças de estrutura do banco: **backup primeiro**, depois o script de migração (como `scripts/migracao_002_endereco_doador.py`) apontado para o banco da nuvem.

## 6. Backup e restauração

- **Banco local:** `scripts/auditar_e_backup_banco.ps1`
- **Banco da nuvem:** `scripts/backup_nuvem.ps1 -Servidor <host público> -Porta <porta> -Usuario <usuário> -Banco <banco>` (dados de conexão na aba *Connect* do serviço MySQL). O plano de teste do Railway não faz backup automático.
- **Restaurar** num banco vazio: `mysql -h HOST -P PORTA -u USUÁRIO -p --ssl-mode=REQUIRED BANCO < arquivo.sql`
- Os backups ficam em `Documents\HemoFlow_backups` e nunca vão para o GitHub (o `.gitignore` bloqueia `*.sql` fora de `banco/`).

## 7. Limitações conhecidas

- **Prazo do teste gratuito:** o crédito do Railway vale por 30 dias. Quando acabar, os serviços param; para continuar no ar é preciso escolher um plano pago ou outra hospedagem.
- As sessões ficam na memória do servidor: cada nova publicação desconecta quem estava logado.
- O plano B para uma apresentação sem a nuvem é rodar no computador com `iniciar_hemoflow.ps1`.
