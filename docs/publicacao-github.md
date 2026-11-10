# Publicação no GitHub

## 1. Preparar a conta e o repositório

Entre no GitHub pela sua própria conta e crie um repositório **vazio** chamado `hemoflow`. Não inclua README, licença ou `.gitignore` inicial, pois eles já existem neste projeto. O endereço remoto ficará parecido com `https://github.com/SEU-USUARIO/hemoflow.git`.

## 2. Instalar/configurar o Git localmente

Instale o Git se necessário e configure sua identificação para os commits:

```bash
git config --global user.name "Seu Nome"
git config --global user.email "seu-email@example.com"
```

Use um e-mail verificado na sua conta ou o endereço privado fornecido pelo GitHub. Não coloque senha, token de acesso ou chave privada em arquivos do projeto.

## 3. Enviar o projeto

Abra um terminal dentro da pasta `hemoflow` e rode:

```bash
git init
git branch -M main
git add .
git status --short
git commit -m "feat: versão inicial do HemoFlow"
git remote add origin https://github.com/SEU-USUARIO/hemoflow.git
git push -u origin main
```

Substitua `SEU-USUARIO`. Quando solicitado, autentique-se com o método recomendado pelo GitHub. O GitHub não aceita a senha normal da conta como autenticação Git por HTTPS; use o navegador/Git Credential Manager ou um token pessoal configurado com segurança no seu computador.

## 4. Conferir

Atualize a página do repositório no GitHub e confira se aparecem README, `app_mysql.py`, `static/`, `sql/`, `scripts/`, `docs/` e `tests/`. Backups (`*.sql` fora de `sql/`), arquivos `.env`, credenciais e dados locais são excluídos pelo `.gitignore`.
