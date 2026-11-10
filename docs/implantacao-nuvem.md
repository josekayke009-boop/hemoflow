# Implantação do HemoFlow na nuvem

Preparado em 10/11/2026. **Nada foi contratado nem criado.** A escolha do serviço e qualquer custo dependem da sua autorização.

## 1. Arquitetura

```
Navegador ──HTTPS──► Proxy da hospedagem (certificado automático)
                         │  HTTP interno + X-Forwarded-For
                         ▼
                   Contêiner Python (Dockerfile)
                   app_mysql.py: API + interface (static/)
                         │  pool de conexões, TLS quando a rede é pública
                         ▼
                   MySQL 8 gerenciado ──► backups (provedor + scripts/backup_nuvem.ps1)
```

- **Mesma arquitetura de hoje:** Python + MySQL + HTML/CSS/JS. O frontend continua sendo servido pelo próprio backend, então não há um segundo serviço para hospedar.
- **Arquivos enviados pelo usuário:** o sistema não armazena arquivos. Os relatórios ainda não têm exportação. Por isso não é preciso armazenamento de arquivos agora.
- **Segredos:** ficam só nas variáveis de ambiente do painel da hospedagem (modelo em `.env.example`). Nada vai no código nem no GitHub.

## 2. O que foi preparado no código

| Item | Onde |
|---|---|
| Modo produção (`HEMOFLOW_ENV=production`): escuta em `0.0.0.0`, usa a porta `PORT` da plataforma, cookie `Secure`, HSTS | `app_mysql.py` |
| Conexão MySQL com TLS (`required` / `verify` com certificado) | `HEMOFLOW_DB_SSL`, `HEMOFLOW_DB_SSL_CA(_PEM)` |
| Pool de conexões (antes: 2 a 4 conexões novas por requisição) | `HEMOFLOW_DB_POOL_SIZE` |
| Fuso America/Recife para vencimentos e para o `NOW()` do MySQL (a nuvem roda em UTC) | `HEMOFLOW_TZ` |
| IP real atrás do proxy (limite de tentativas de login por IP) | `HEMOFLOW_TRUST_PROXY`, `HEMOFLOW_PROXY_HOPS` |
| Bloqueio da conta por 15 min após 5 senhas erradas seguidas | login |
| Cabeçalhos CSP, X-Frame-Options, nosniff | todas as respostas |
| Link de recuperação de senha com o endereço público | `HEMOFLOW_PUBLIC_URL` |
| Verificação de saúde para a plataforma | `GET /healthz` |
| Imagem de contêiner sem usuário root | `Dockerfile`, `.dockerignore` |
| Banco novo: estrutura + dados de referência, **sem dados pessoais** | `scripts/instalar_banco_nuvem.py`, `sql/instalacao/` |
| Primeiro administrador no banco remoto | `setup_admin.py` (usa as mesmas variáveis) |
| Backup do banco da nuvem para o computador | `scripts/backup_nuvem.ps1` |
| Dependências | `requirements.txt` |

Nenhum caminho do Windows é usado pelo app. Os caminhos são relativos ao próprio `app_mysql.py`.

## 3. Comparação de hospedagens (preços pesquisados em 10/11/2026: confirme na hora de contratar)

| | **A. Railway (Hobby)** | **B. Render + Aiven** | **C. Oracle Cloud Always Free** |
|---|---|---|---|
| App Python | contêiner (Dockerfile) | Render Starter (0,5 CPU, 512 MB) | VM Always Free |
| MySQL | serviço MySQL no mesmo projeto | Aiven Developer (1 GB RAM, 8 GB) | HeatWave MySQL Always Free (50 GB + 50 GB de backup) |
| **Custo mensal** | **US$ 5** (inclui US$ 5 de uso; o que passar é cobrado; dá para definir limite de gasto) | **≈ US$ 12** (US$ 7 + US$ 5) | **US$ 0** (pede cartão para verificação) |
| Plano gratuito | só crédito de teste único | Render Free **dorme após 15 min** (≈1 min para acordar); **o MySQL gratuito da Aiven foi descontinuado** (novos desde 06/11/2026; os existentes desligados em 21/12/2026) | sim, sem prazo, sem SLA |
| Facilidade | ★★★ (conecta no GitHub, HTTPS e domínio automáticos) | ★★☆ (dois painéis) | ★☆☆ (rede virtual, firewall, HTTPS e atualizações por sua conta) |
| Segurança | rede privada entre app e banco; HTTPS automático | TLS obrigatório no MySQL; HTTPS automático | depende de você configurar e manter |
| Backup automático | **não no Hobby** (só no Pro): usar `scripts/backup_nuvem.ps1` | sim (Aiven) | sim, diário, guardado por 1 dia |
| Desempenho | bom para a turma | bom | bom, mas o limite de VM gratuita foi reduzido em 2026 |
| Crescimento | sobe de plano sem migrar | sobe de plano | limitado ao gratuito, depois pago |
| Disponibilidade | sem SLA no Hobby | SLA nos planos pagos | sem SLA |

**Recomendação para o projeto acadêmico: A (Railway Hobby).** É a opção com menos passos e menos chance de erro antes da apresentação: app e banco no mesmo lugar, HTTPS automático e atualização a cada `git push`. A ressalva é o backup, que no Hobby precisa ser manual (script pronto). **C** é a opção de custo zero, mas exige administrar um servidor Linux. **B** custa mais que A sem vantagem clara para este uso.

## 3.1 Opção gratuita até o fim de novembro/2026 (pedido em 10/11/2026)

O sistema só precisa ficar no ar até 30/11/2026 (cerca de 20 dias). Opções sem pagar:

| | **Teste grátis do Railway** (recomendado) | Túnel gratuito (Cloudflare) a partir do notebook | Oracle Always Free |
|---|---|---|---|
| Custo | US$ 0: crédito único de US$ 5, válido por 30 dias, **sem cartão** | US$ 0, sem cadastro | US$ 0 (cartão só para verificação) |
| Depende do notebook ligado? | não | **sim**: notebook, MySQL e servidor ligados | não |
| Endereço | `https://<nome>.up.railway.app` | `https://<aleatório>.trycloudflare.com` (muda a cada vez) | IP ou domínio próprio |
| Trabalho | o mesmo já preparado (seção 4) | 1 comando | alto (servidor Linux) |
| Risco | se os US$ 5 acabarem antes, os serviços param; os dados são apagados 30 dias depois do fim do crédito | cai se o notebook dormir ou desligar | configuração demorada |

**Estimativa de consumo no Railway** (US$ 10 por GB de RAM/mês, US$ 20 por vCPU/mês): MySQL com memória reduzida (~300 MB) + app (~80 MB) ≈ US$ 4/mês, ou seja, ≈ US$ 2,70 por 20 dias. Cabe no crédito, com folga pequena. Para economizar:
- no serviço MySQL, adicionar ao comando de início `--performance-schema=OFF --innodb-buffer-pool-size=64M`;
- `HEMOFLOW_DB_POOL_SIZE=3`;
- acompanhar o consumo na aba *Usage* uma vez por semana.

**Plano B para o dia da apresentação:** se algo der errado na nuvem, o túnel gratuito publica o sistema local pela internet com HTTPS em 1 minuto (`cloudflared tunnel --url http://127.0.0.1:8000`).

## 4. Passo a passo (opção A, Railway): só depois da sua autorização

1. Repositório no GitHub (ver `README.md`). O Railway publica a partir dele.
2. Railway: criar projeto → **Deploy from GitHub** (o `Dockerfile` é detectado) → adicionar o serviço **MySQL**.
3. Definir um limite de gasto (*usage limit*) no painel, para não haver cobrança surpresa.
4. Variáveis do serviço do app (aba *Variables*), conforme o `.env.example`:
   - `HEMOFLOW_ENV=production`, `HEMOFLOW_TZ=America/Recife`
   - `HEMOFLOW_DB_HOST/PORT/NAME/USER/PASSWORD` apontando para o MySQL do projeto (referências `${{MySQL.MYSQLHOST}}` etc.)
   - `HEMOFLOW_DB_SSL=required` (o MySQL 8 exige conexão segura para autenticar; funciona também pela rede privada).
   - `HEMOFLOW_PUBLIC_URL=https://<endereço gerado>.up.railway.app`
5. Instalar a estrutura no banco novo, do seu computador, usando o endereço público (TCP proxy) do MySQL:
   `python scripts/instalar_banco_nuvem.py`
6. Criar o administrador no banco da nuvem:
   ```powershell
   $env:HEMOFLOW_DB_HOST="<host público>"; $env:HEMOFLOW_DB_PORT="<porta>"; $env:HEMOFLOW_DB_USER="<usuário>"; $env:HEMOFLOW_DB_NAME="<banco>"; $env:HEMOFLOW_DB_SSL="required"
   python setup_admin.py
   ```
7. Abrir `https://.../healthz` → `{"ok": true, "banco": "ok"}`.
8. Teste final pela internet (seção 6).

**Dados:** a nuvem começa **vazia**, só com perfis, permissões, tipos sanguíneos e hemocomponentes. Os doadores e as bolsas do banco local **não** são copiados. Copiar só com a sua autorização, e apenas se forem dados fictícios.

## 5. Desenvolvimento x produção

| | Local (desenvolvimento) | Nuvem (produção) |
|---|---|---|
| Iniciar | `.\iniciar_hemoflow.ps1` | automático a cada `git push` |
| `HEMOFLOW_ENV` | `development` (padrão) | `production` |
| Endereço | http://127.0.0.1:8000 | https://... |
| Banco | MySQL do notebook | MySQL do provedor |
| Cookie Secure / HSTS | não | sim |

## 6. Checklist do teste final (Etapa 7)

- [ ] `/healthz` responde `ok` pela internet
- [ ] Login do administrador por HTTPS; o cookie aparece com `Secure`
- [ ] Senha errada → 401; 5 seguidas → conta bloqueada por 15 min
- [ ] Cadastrar doador; e-mail repetido → bloqueado
- [ ] Cadastrar profissional; e-mail repetido → bloqueado
- [ ] Criar conta de acesso; seleção dos 4 perfis
- [ ] Conta CONSULTA não acessa nada administrativo
- [ ] Bolsa: cadastro, reserva, liberação, histórico
- [ ] Datas de vencimento corretas no horário de Recife
- [ ] Acesso pelo celular (4G, fora da rede de casa)

## 7. Atualizar a aplicação

1. Alterar e testar localmente (`python -m unittest discover -s tests -v` e `.\iniciar_hemoflow.ps1`).
2. `git add` / `git commit` / `git push`. A plataforma reconstrói e publica sozinha.
3. Mudanças de estrutura do banco: **backup primeiro**, depois um script de migração (como `scripts/migracao_001_email_unico.py`) apontado para o banco da nuvem.

## 8. Backup e restauração

- **Local:** `scripts/auditar_e_backup_banco.ps1`
- **Nuvem:** `scripts/backup_nuvem.ps1 -Servidor <host> -Porta <porta> -Usuario <usuário> -Banco <banco>`. Recomendado semanalmente e antes de toda migração.
- **Restaurar** num banco vazio: `mysql -h HOST -P PORTA -u USUÁRIO -p --ssl-mode=REQUIRED BANCO < arquivo.sql`
- Os arquivos de backup ficam em `Documents\HemoFlow_backups` e **nunca** vão para o GitHub (`.gitignore` bloqueia `*.sql` fora de `sql/`).

## 9. Limitações conhecidas

- As sessões ficam na memória do servidor: cada nova publicação desconecta quem estiver logado. Para uma única instância (caso do projeto), isso é aceitável. A tabela `sessoes` já existe para uma evolução futura.
- A recuperação de senha precisa de SMTP (Gmail com senha de app) e da tabela `recuperacao_senhas`, que já vem no instalador da nuvem e ainda **não** existe no banco local.

## Fontes de preços

- Railway: [planos (documentação oficial)](https://docs.railway.com/pricing/plans), [backups no Hobby (fórum)](https://station.railway.com/questions/backups-hobby-plan-dacb8ba4)
- Aiven: [fim do MySQL gratuito](https://aiven.io/free-mysql-database), [changelog](https://aiven.io/changelog), [preços MySQL](https://aiven.io/pricing/mysql)
- Render: [Free x Starter](https://actualdatabase.com/render-free-vs-starter-pricing/), [preços 2026](https://temps.sh/blog/render-pricing-2026)
- Oracle: [recursos Always Free](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm), [HeatWave Always Free](https://blogs.oracle.com/mysql/heatwave-mysql-always-free-tier)
