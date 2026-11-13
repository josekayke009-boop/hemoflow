# HemoFlow

Sistema web acadêmico de gerenciamento de banco de sangue: doadores, profissionais, contas de acesso com perfis, bolsas, estoque e movimentações. Projeto Inovadores, ADS (4º período), UNINASSAU.



**Sistema no ar:** https://hemoflow-production.up.railway.app  
**Código:** https://github.com/josekayke009-boop/hemoflow

<img src="docs/qrcode/qrcode-hemoflow.png" alt="QR Code para abrir o HemoFlow no celular" width="180">

Aponte a câmera do celular para abrir o HemoFlow. Para instalar como aplicativo: Android (Chrome) → menu → **Instalar aplicativo**; iPhone (Safari) → Compartilhar → **Adicionar à Tela de Início**.

## Arquitetura

- **Backend:** Python (biblioteca padrão `http.server`) em `app_mysql.py`
- **Banco:** MySQL 8.0 via `mysql-connector-python`
- **Frontend:** HTML, CSS e JavaScript em `static/`, servidos pelo próprio backend
- **Autenticação:** sessão por cookie `HttpOnly`, senhas com PBKDF2-SHA256, permissões por perfil checadas no servidor

## Requisitos

- Python 3.10 ou superior
- MySQL 8.0 com o banco `hemoflow` e o usuário `hemoflow_app`
- `pip install -r requirements.txt`

## Executar (Windows)

```powershell
.\iniciar_hemoflow.ps1            # porta 8000
.\iniciar_hemoflow.ps1 -Porta 8001
```

O script pede a senha do usuário MySQL `hemoflow_app` sem exibi-la. Depois, abra http://127.0.0.1:8000.

Variáveis de ambiente aceitas: `HEMOFLOW_DB_HOST`, `HEMOFLOW_DB_PORT`, `HEMOFLOW_DB_NAME`, `HEMOFLOW_DB_USER`, `HEMOFLOW_DB_PASSWORD`, `HEMOFLOW_HOST`, `HEMOFLOW_PORT`, `HEMOFLOW_EMAIL_USER`, `HEMOFLOW_EMAIL_PASSWORD`.

## Primeiro administrador

```powershell
python setup_admin.py
```

## Banco de dados: scripts

| Script | Função | Altera o banco? |
|---|---|---|
| `scripts/auditar_e_backup_banco.ps1` | backup completo + estrutura + relatório de auditoria em `..\HemoFlow_backups\` | não |
| `scripts/migracao_001_email_unico.py` | e-mail único em doadores e profissionais (`--verificar`, `--reverter`) | sim, reversível |
| `sql/criar_recuperacao_senhas.sql` | tabela de recuperação de senha | sim (só cria) |
| `scripts/instalar_banco_nuvem.py` | cria a estrutura num MySQL novo (nuvem), sem dados pessoais | sim (banco vazio) |
| `scripts/backup_nuvem.ps1` | backup do banco da nuvem | não |
| `scripts/migracao_002_endereco_doador.py` | endereço do doador (`--verificar`, `--reverter`) | sim, reversível |
| `scripts/migracao_003_recuperacao_senha.py` | tabela da recuperação de senha | sim (só cria) |
| `scripts/redefinir_senha_app.py` | nova senha para o usuário `hemoflow_app` (pede a do root) | só a senha |
| `migrar_cadastros.py` | colunas de tipo sanguíneo e peso em `doadores` | sim (só adiciona) |

Alterações de estrutura devem ser feitas com um usuário administrativo (ex.: `root`); `hemoflow_app` não tem permissão de `CREATE`. **Faça o backup antes.**

## Testes

```powershell
python -m unittest discover -s tests -v
```

## Documentação

- `docs/auditoria-2026-11-10.md`: diagnóstico técnico e plano de execução
- `docs/testes-2026-11-10.md`: registro de testes
- `docs/implantacao-nuvem.md`: arquitetura na nuvem, comparação de hospedagens, passo a passo, backup e atualização
- `docs/arquitetura.md` e `docs/banco-de-dados.md` ainda descrevem a versão SQLite antiga e serão reescritos a partir da estrutura real do MySQL.

A versão SQLite antiga (`app.py`, `hemoflow.db`) foi retirada do projeto e guardada em `Documents\HemoFlow_SQLite_antigo`.
