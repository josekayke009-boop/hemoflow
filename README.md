# HemoFlow

Sistema web para gestão de hemocentro: cadastro de doadores e profissionais, controle do estoque de bolsas de sangue, movimentações, alertas e contas de acesso com perfis.

Projeto da disciplina **Projeto Inovadores** — Análise e Desenvolvimento de Sistemas (4º período), UNINASSAU.

- **Sistema no ar:** https://hemoflow-production.up.railway.app
- **Código:** https://github.com/josekayke009-boop/hemoflow

<img src="docs/qrcode/qrcode-hemoflow.png" alt="QR Code para abrir o HemoFlow no celular" width="170">

Aponte a câmera do celular para abrir o sistema. Ele também pode ser instalado como aplicativo: no Android (Chrome), menu → **Instalar aplicativo**; no iPhone (Safari), Compartilhar → **Adicionar à Tela de Início**.

## Funcionalidades

| Área | O que faz |
|---|---|
| Login e acesso | Login com sessão segura, bloqueio após tentativas erradas, recuperação de senha por e-mail |
| Perfis | Administrador, Responsável técnico, Operador de estoque e Consulta, com permissões verificadas no servidor |
| Doadores | Cadastro com CPF validado (sem repetir e parcialmente oculto na lista, LGPD), endereço, máscaras, e-mail único, revisão anual e exclusão |
| Profissionais | Cadastro de profissionais licenciados (e-mail e registro únicos) |
| Bolsas e estoque | Registro de bolsas, estoque por tipo sanguíneo, validade e situação (disponível, reservada, quarentena...) |
| Movimentações | Reserva, liberação, transfusão e descarte, com histórico |
| Alertas | Notificações de estoque crítico, bolsas vencendo/vencidas e cadastros desatualizados |
| Relatórios | Indicadores do estoque e distribuição por tipo sanguíneo |
| Suporte | Aba para enviar dúvidas, problemas e sugestões por e-mail à equipe, com número de protocolo |
| Aplicativo | Instalável no celular e no computador (PWA), com consulta do estoque sem internet |

## Tecnologias

- **Backend:** Python 3 (biblioteca padrão `http.server`) — `servidor.py`
- **Banco de dados:** MySQL 8 (`mysql-connector-python`)
- **Frontend:** HTML, CSS e JavaScript, sem frameworks — pasta `static/`
- **Hospedagem:** Railway (contêiner Docker + MySQL), publicação automática a cada envio ao GitHub

## Estrutura do projeto

```
hemoflow/
├── servidor.py              Servidor: API, login, permissões e regras do sistema
├── static/                  Telas do sistema
│   ├── index.html           Página única (login, menu, janelas)
│   ├── css/estilos.css      Estilos
│   ├── js/app.js            Lógica das telas (cada tela e botão comentado por seção)
│   ├── js/fundo-login.js    Animação da tela de login
│   ├── img/ e icons/        Logo, ícones do aplicativo e imagens do login
│   └── manifest.webmanifest e sw.js   Aplicativo instalável
├── banco/
│   ├── instalacao/          SQL para criar o banco do zero (estrutura e dados de referência)
│   └── migracoes/           Alterações de estrutura, com o script para desfazer
├── scripts/                 Backup, migrações, criação do administrador e utilitários
├── tests/                   Testes automatizados
├── docs/                    Documentação (arquitetura, banco, testes, implantação, apresentação)
├── iniciar_hemoflow.ps1     Inicia o sistema no Windows
├── Dockerfile               Imagem usada na nuvem
├── requirements.txt         Dependências Python
└── .env.example             Modelo das variáveis de configuração (sem senhas)
```

## Como executar no computador

Pré-requisitos: Python 3.10 ou superior e MySQL 8 com o banco `hemoflow` criado.

```powershell
pip install -r requirements.txt
.\iniciar_hemoflow.ps1
```

O script pede a senha do usuário `hemoflow_app` do MySQL (e, opcionalmente, o Gmail usado na recuperação de senha). Depois é só abrir http://127.0.0.1:8000.

Primeiro acesso: crie o administrador com

```powershell
python scripts/criar_administrador.py
```

Para criar o banco do zero use `scripts/instalar_banco_nuvem.py` (funciona também num MySQL local vazio). As alterações de estrutura ficam em `scripts/migracao_*.py` e devem ser executadas com um usuário administrativo do MySQL, sempre depois de um backup (`scripts/auditar_e_backup_banco.ps1`).

## Testes

```powershell
python -m unittest discover -s tests -v
```

São 75 testes automatizados (cadastros, CPF, suporte, envio de e-mail, segurança, notificações e recuperação de senha). Os resultados dos testes manuais estão em [docs/relatorio-testes.md](docs/relatorio-testes.md).

## Perfis de acesso

| Perfil | Pode |
|---|---|
| Administrador | Tudo, inclusive contas de acesso e cadastro de profissionais |
| Responsável técnico | Doadores, bolsas e todas as movimentações |
| Operador de estoque | Registrar bolsas, reservar, liberar e colocar em quarentena |
| Consulta | Apenas visualizar |

## Documentação

- [Arquitetura](docs/arquitetura.md) — como as partes se comunicam
- [Banco de dados](docs/banco-de-dados.md) — tabelas e relacionamentos
- [Implantação](docs/implantacao.md) — nuvem, variáveis, atualização e backup
- [Relatório de testes](docs/relatorio-testes.md)
- [Relatório de auditoria](docs/relatorio-auditoria.md) — diagnóstico inicial do projeto
- [Roteiro de apresentação](docs/roteiro-apresentacao.md)

## Autoria

Desenvolvido por Jose Kaike — Análise e Desenvolvimento de Sistemas, UNINASSAU.

Desenvolvido com apoio de ferramentas de IA para revisão e testes.
