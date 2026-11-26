# Registro de testes: 10/11/2026 (correção de e-mail duplicado)

> **Nota:** este relatório foi escrito antes da reorganização das pastas e cita os nomes de arquivo da época. Correspondência atual: `app_mysql.py` → `servidor.py`; `setup_admin.py` → `scripts/criar_administrador.py`; `migrar_cadastros.py` → `scripts/migracao_000_tipo_sanguineo_peso.py`; `sql/` → `banco/`; `static/app.js` → `static/js/app.js`; `static/styles.css` → `static/css/estilos.css`; `tests/test_cadastros_mysql.py` → `tests/test_cadastros.py`; `tests/test_producao.py` → `tests/test_seguranca.py`. Os resultados registrados não foram alterados.

Comando: `python -m unittest discover -s tests -v` · Python 3.14.0 · resultado: **18 executados, 18 aprovados**.

Os testes de `test_cadastros_mysql.py` usam um banco **simulado**. Eles comprovam as regras do backend, mas **não** comprovam o comportamento do MySQL real. Esses itens aparecem abaixo como **não executados** até a migração ser aplicada e o teste ser feito no navegador.

| # | Teste | Resultado |
|---|---|---|
| 1 | Doador novo é gravado (e-mail em minúsculas) | Aprovado (simulado) |
| 2 | Doador com e-mail já cadastrado → 409, nada gravado | Aprovado (simulado) |
| 3 | Dois cadastros simultâneos: erro 1062 do UNIQUE vira 409 + rollback | Aprovado (simulado) |
| 4 | Doador com e-mail inválido → 400 | Aprovado |
| 5 | Doador sem telefone (campo obrigatório) → 400 | Aprovado |
| 6 | Profissional novo grava o e-mail | Aprovado (simulado) |
| 7 | Profissional com e-mail já cadastrado → 409, nada gravado | Aprovado (simulado) |
| 8 | Profissional simultâneo: 1062 do UNIQUE vira 409 | Aprovado (simulado) |
| 9 | Profissional sem e-mail → 400 | Aprovado |
| 10 | Migração pendente → 503 com instrução, nada gravado | Aprovado (simulado) |
| 11 | Não administrador cadastrando profissional → 403 | Aprovado |
| 12 | Sem sessão → 401 | Aprovado |
| 13 | Detecção de migração pendente/aplicada | Aprovado (simulado) |
| 14–18 | Testes antigos do `app.py` (SQLite legado) | Aprovados |
| — | Migração 001 aplicada no MySQL real (3 passos OK, estado final "aplicado") | **Aprovado** |
| — | Bloqueio de duplicidade no navegador com MySQL real | **Não executado** |

## Testes no sistema real: servidor local + MySQL 8.0.46 (10/11/2026, após a migração 001)

Executados no navegador do app, com a sessão do administrador aberta pela usuária/usuário, e por `curl` com uma conta de teste de perfil CONSULTA. Todos os registros criados têm "TESTE" no nome (sufixo `7290544`).

| # | Teste | Esperado | Obtido | Resultado |
|---|---|---|---|---|
| R1 | Sessão do administrador | perfil ADMINISTRADOR, 34 permissões | igual | Aprovado |
| R2 | Comunicação com o banco: painel, bolsas, movimentações, doadores | 200 | 200 em todas | Aprovado |
| R3 | Carregar perfis (`/api/access-accounts`) | 4 perfis | ADMINISTRADOR, RESPONSAVEL_TECNICO, OPERADOR_ESTOQUE, CONSULTA | Aprovado |
| R4 | Tela Contas de acesso: seleção de perfil | lista preenchida | "Selecione o perfil" + 4 perfis; tabela com contas | Aprovado |
| R5 | Cadastrar doador | 201 | 201 "Doador cadastrado com sucesso." | Aprovado |
| R6 | Doador com e-mail repetido | 409 | 409 "Já existe um doador cadastrado com esse e-mail." | Aprovado |
| R7 | Doador com e-mail repetido em MAIÚSCULAS | 409 | 409 | Aprovado |
| R8 | Doador repetido pelo formulário da tela | mensagem na tela | "Já existe um doador cadastrado com esse e-mail." | Aprovado |
| R9 | Doador sem telefone (obrigatório) | 400 | 400 "Informe o telefone." | Aprovado |
| R10 | Cadastrar profissional com e-mail | 201 | 201 | Aprovado |
| R11 | Profissional com e-mail repetido | 409 | 409 "Já existe um profissional cadastrado com esse e-mail." | Aprovado |
| R12 | Profissional sem e-mail | 400 | 400 "Informe um e-mail válido." | Aprovado |
| R13 | Criar conta de acesso (perfil CONSULTA) | 201 | 201 | Aprovado |
| R14 | Conta com e-mail repetido | 409 | 409 "Já existe uma conta cadastrada com esse e-mail." | Aprovado |
| R15 | Conta com perfil inexistente | 400 | 400 | Aprovado |
| R16 | Conta com senha curta | 400 | 400 | Aprovado |
| R17 | Cadastrar bolsa | 201 | 201 (HF-8499B62916) | Aprovado |
| R18 | Cadastrar bolsa já vencida | 400 | 400 | Aprovado |
| R19 | Reservar bolsa / liberar de novo | 200 / 200 | 200 / 200 | Aprovado |
| R20 | Transição inválida (RESERVADA → RESERVADA) | 409 | 409 | Aprovado |
| R21 | Histórico da bolsa | entrada, reserva, liberação | `null→DISPONIVEL`, `DISPONIVEL→RESERVADA`, `RESERVADA→DISPONIVEL` | Aprovado |
| R22 | Filtro de bolsas (tipo A-, busca "TESTE") | 1 | 1 | Aprovado |
| R23 | Login com senha errada | 401 | 401 | Aprovado |
| R24 | Acesso sem login | 401 | 401 | Aprovado |
| R25 | Login da conta CONSULTA | 200 | 200 | Aprovado |
| R26 | CONSULTA pode ver painel, bolsas e doadores | 200 | 200 | Aprovado |
| R27 | CONSULTA tenta ver ou criar contas, criar profissional, doador ou bolsa, ou movimentar | 403 | 403 em todas | Aprovado |
| R28 | Logout encerra a sessão | 401 depois | 401 | Aprovado |
| R29 | **Navegação em tela de celular** | menu permite trocar de tela | **a barra inferior só mostra o item da página atual (nenhum, em Contas de acesso), e o botão do topo fica cortado** | **Reprovado** (corrigido e retestado em R32–R36) |
| R30 | Recuperação de senha | — | não testado: a tabela `recuperacao_senhas` não existe e o SMTP não está configurado | Não executado |
| R31 | Acesso pela internet | — | depende da implantação (Etapa 6) | Não executado |

### Reteste após as correções de interface (mesmo dia)

Defeitos corrigidos: o menu do celular não navegava (R29); o botão "Sair" ficava escondido em telas menores que 1300 px; as listas apareciam vazias por até 60 s depois de recarregar a página (F5); o item marcado no menu não correspondia à tela aberta depois de recarregar; o nome "HemoFlow" vazava da barra lateral no tablet.

| # | Teste | Obtido | Resultado |
|---|---|---|---|
| R32 | Celular 375 px: menu inferior | os 10 itens disponíveis, rolagem horizontal, item atual destacado e visível | Aprovado |
| R33 | Celular: tocar em "Doadores" no menu | abriu Doadores, item destacado | Aprovado |
| R34 | Celular: topo sem cortar, com "Sair" | largura da página = 375 px, botão Sair visível | Aprovado |
| R35 | Recarregar (F5) em Doadores | lista carregada na hora (8 doadores) | Aprovado |
| R36 | Tablet 768 px e computador 1280 px | sem rolagem lateral; logo sem texto vazando; Sair visível; estoque com 3 bolsas | Aprovado |
| R37 | Testes automatizados (`unittest`) | 13/13 aprovados | Aprovado |

## Reteste da versão preparada para a nuvem (código de produção, MySQL local, porta 8001)

Defeito encontrado e corrigido durante o reteste: a primeira versão desligava o TLS na conexão local, e o MySQL 8 recusava a autenticação (`2061 Authentication requires secure connection`). O padrão local passou a ser `preferred`.

| # | Teste | Obtido | Resultado |
|---|---|---|---|
| P1 | Conexão com o MySQL usando pool + TLS `preferred` | servidor iniciou; `/healthz` → `{"ok": true, "banco": "ok"}` | Aprovado |
| P2 | Cabeçalhos CSP e X-Frame-Options | presentes | Aprovado |
| P3 | 5 consultas seguidas pelo pool | 200 em todas | Aprovado |
| P4 | 5 senhas erradas seguidas na mesma conta (conta TESTE CONSULTA) | 401 × 5 | Aprovado |
| P5 | Senha **certa** logo depois | 429 "Conta bloqueada temporariamente…" | Aprovado |
| P6 | "Esqueceu sua senha?" sem SMTP configurado | 503 "envio de e-mail ainda não está configurado" (igual para qualquer e-mail) | Aprovado |
| P7 | Sessão do administrador, painel, bolsas, movimentações, doadores e 4 perfis | 200 / 4 perfis | Aprovado |
| P8 | Doador novo / e-mail repetido | 201 / 409 | Aprovado |
| P9 | Profissional novo / e-mail repetido | 201 / 409 | Aprovado |
| P10 | Bolsa nova + reserva | 201 (HF-3EF344ED1F) / 200 | Aprovado |
| P11 | Horário gravado pelo MySQL (fuso da sessão −03:00) | 13:40:15 no banco = 13:40:15 em Recife | Aprovado |
| P12 | Interface com a política de segurança: fontes, logo, telas | carregam, sem erro de CSP no console | Aprovado |
| P13 | Testes automatizados | 24/24 | Aprovado |

## Exclusão de doadores e ajustes de texto (pedido de 10/11/2026), servidor na porta 8002

| # | Teste | Obtido | Resultado |
|---|---|---|---|
| D1 | Coluna "Ação" e botão Excluir para o administrador | 9 linhas, 9 botões | Aprovado |
| D2 | Excluir um doador de teste pela API | 200 "Doador excluído."; total 9 → 8 | Aprovado |
| D3 | Excluir um doador inexistente | 404 "Doador não encontrado." | Aprovado |
| D4 | Botão Excluir → Cancelar na confirmação | doador continua na lista | Aprovado |
| D5 | Botão Excluir → Confirmar | aviso "Doador excluído.", linha removida | Aprovado |
| D6 | Doador com doações ou agendamentos | 409, nada apagado (teste automatizado; o banco não tem doações para testar no real) | Aprovado (simulado) |
| D7 | Perfil sem `doadores.editar` / sem login | 403 / 401 (testes automatizados) | Aprovado |
| D8 | Rodapé da barra lateral | "HEMOFLOW" | Aprovado |
| D9 | Fim da tela Cadastros sem os avisos de protótipo, CPF e e-mail | nenhum aviso; CPF com o formato `000.000.000-00` | Aprovado |
| D10 | Testes automatizados | 29/29 | Aprovado |

## Notificações do sistema e remoção da aba Comunicação (servidor na porta 8003)

| # | Teste | Obtido | Resultado |
|---|---|---|---|
| N1 | Aba Comunicação fora do menu | menu com 9 itens, sem Comunicação | Aprovado |
| N2 | Preferência desativada pelo usuário | sino sem número; painel "As notificações estão desativadas." | Aprovado |
| N3 | Ligar em Configurações | "Notificações ativadas."; preferência gravada no MySQL (`configuracoes`) | Aprovado |
| N4 | Alertas de estoque com o banco real | 8 alertas críticos (5 tipos com 0 bolsas, 3 tipos com 1); número 8 no sino | Aprovado |
| N5 | Preferência mantida depois de recarregar (F5) | sino continua com 8 | Aprovado |
| N6 | Clique num alerta | abre "Estoque de sangue" e fecha o painel | Aprovado |
| N7 | Desligar de novo (estado original restaurado) | interruptor desligado, sino sem número | Aprovado |
| N8 | Painel no celular (375 px) e no computador (1280 px) | dentro da tela, sem rolagem lateral | Aprovado |
| N9 | Lista de doadores com o campo de revisão | campo presente; 0 doadores com mais de 1 ano (todos cadastrados em 2026) | Aprovado |
| N10 | Alertas de validade, cadastro com mais de 1 ano, revisão, permissões e preferência inválida | testes automatizados (o banco real não tem casos assim hoje) | Aprovado (simulado) |
| N11 | Testes automatizados | 38/38 | Aprovado |

## 11/11/2026: baixa nas notificações e reteste da exclusão (servidor na porta 8000)

Defeitos encontrados e corrigidos:
- **Exclusão com erro (relatado pelo usuário em 10/11):** o servidor da porta 8000 ainda rodava a versão anterior, sem a rota de exclusão. As telas novas mostravam o botão, o servidor respondia 501, e a tela mostrava a mensagem genérica. Corrigido: mensagem clara para esse caso. Também corrigido o corte de conexão intermitente no Windows quando o servidor respondia sem ler o corpo da requisição (testes 403 falhavam às vezes com `WinError 10053`).
- **Lista de notificações desatualizada logo após a baixa:** uma busca iniciada antes da baixa sobrescrevia a lista. Corrigido: só a resposta mais recente é aplicada.

| # | Teste | Obtido | Resultado |
|---|---|---|---|
| E1 | Excluir doador de teste pelo botão (com confirmação) | "Doador excluído."; 8 → 7 linhas; removido do banco | Aprovado |
| B1 | Clicar numa notificação não vista | abre a tela do alerta; sino 5 → 4; o item fica "Vista" | Aprovado |
| B2 | Lista e número coerentes após o clique | 4 não vistas na lista = 4 no sino | Aprovado |
| B3 | "Marcar todas como vistas" | sino sem número; "Todas vistas" | Aprovado |
| B4 | Recarregar a página (F5) | continua sem número (gravado no banco) | Aprovado |
| B5 | Situação muda → alerta volta a contar; chave inválida; por usuário | testes automatizados | Aprovado (simulado) |
| B6 | Testes automatizados (6 execuções seguidas) | 43/43 em todas | Aprovado |

## 11/11/2026: endereço, máscaras, confirmação própria, recuperação de senha e olhinho

Migrações aplicadas no MySQL local (com backup `banco_20261111_102326` feito antes): **002** (endereço do doador) e **003** (tabela `recuperacao_senhas`).

Defeitos encontrados e corrigidos:
- O link do e-mail abria a tela de login por cima da tela "Criar nova senha".
- O backup parava com erro vermelho quando a senha do root estava errada: agora pede de novo.
- O script de início aceitava Enter vazio na pergunta do Gmail e seguia sem e-mail: agora só pula com "N".

| # | Teste | Obtido | Resultado |
|---|---|---|---|
| A1 | Cadastro de doador com endereço, máscaras de telefone/CPF/CEP, janela de confirmação e aviso verde ao excluir | conferido pelo usuário no Chrome | Aprovado (usuário) |
| R1 | Gmail com senha de app no início do servidor | "Gmail conectado" | Aprovado |
| R2 | Pedir o link com e-mail cadastrado | e-mail "Redefinição de senha — HemoFlow" chegou no Gmail | Aprovado (usuário) |
| R3 | Abrir o link do e-mail | tela "Criar nova senha" (antes abria o login: corrigido) | Aprovado |
| R4 | Olhinho nos campos de senha | 3 botões na tela; alterna entre texto e senha | Aprovado |
| R5 | Uso único, validade, limite por IP, e-mail não cadastrado, falha do Gmail, conteúdo do e-mail | testes automatizados | Aprovado (simulado) |
| R6 | Testes automatizados | 56/56 | Aprovado |

## 11/11/2026: teste final na nuvem (Railway), https://hemoflow-production.up.railway.app

Implantação: Railway (teste grátis), serviço `hemoflow` (Dockerfile) + serviço MySQL 8 no mesmo projeto, ligados pela rede privada com TLS (`HEMOFLOW_DB_SSL=required`). Estrutura instalada automaticamente no banco vazio (`HEMOFLOW_AUTO_INSTALL=1`), sem expor o MySQL à internet. Administrador criado pelo console do Railway (`setup_admin.py`). Gmail de recuperação configurado nas variáveis do serviço.

| # | Teste | Obtido | Resultado |
|---|---|---|---|
| C1 | Acesso pela internet com HTTPS | página 200; HSTS e CSP presentes | Aprovado |
| C2 | Conexão com o MySQL da nuvem | `/healthz` → `{"ok": true, "banco": "ok"}` | Aprovado |
| C3 | Instalação automática da estrutura | login com e-mail inexistente → 401 (tabela `usuarios` existe); 4 perfis carregados | Aprovado |
| C4 | Login do administrador criado no console | sessão de administrador ativa, permissões carregadas | Aprovado (usuário) |
| C5 | Painel, bolsas, movimentações, doadores, notificações | 200 em todos; 8 alertas de estoque (banco vazio) | Aprovado |
| C6 | Cadastrar doador com endereço | 201; telefone `(81) 98765-4321`, CEP `50030-230`, Recife/PE | Aprovado |
| C7 | E-mail repetido (em maiúsculas) | 409 | Aprovado |
| C8 | Doador sem endereço | 400 "Informe a rua/avenida." | Aprovado |
| C9 | Excluir o doador de teste | 200; banco da nuvem voltou a 0 doadores | Aprovado |
| C10 | Horário na nuvem | cadastro gravado às 11:41:30, horário de Recife | Aprovado |
| C11 | Recuperação de senha configurada | pedido com e-mail inexistente → 200 genérico (sem envio) | Aprovado |
| C12 | Celular 375 px no endereço da nuvem | sem rolagem lateral; menu com 9 itens; campos de endereço | Aprovado |
| C13 | Celular real pelo 4G e e-mail de recuperação chegando com link da nuvem | a confirmar pelo usuário | Pendente |

## 13/11/2026: aplicativo instalável (PWA) e consulta sem internet (nível 1)

O que foi feito: manifesto (`manifest.webmanifest`), ícones (192, 512, maskable e iPhone), service worker (`sw.js`) que guarda só a "casca" do sistema (HTML/CSS/JS/ícones) e nunca as respostas da API, seção "Aplicativo" em Configurações com o botão Instalar e instruções para Android, iPhone e computador, e modo sem conexão só de consulta.

Retrato salvo no aparelho (localStorage): resumo do estoque, bolsas (código, tipo, volume, datas, local, status) e alertas de estoque/validade. **Sem dados pessoais**: nada de doadores, contas, telefones, e-mails, endereços, observações ou responsáveis. Vale por 24 horas e é apagado ao clicar em Sair.

Testes com um servidor que derruba a conexão em `/api/*` (simula a internet caindo):

| # | Teste | Obtido | Resultado |
|---|---|---|---|
| O1 | Sem internet e sem dados salvos | tela de login com "Sem conexão com a internet. Conecte-se para entrar no HemoFlow." | Aprovado |
| O2 | Sem internet com retrato salvo | abre sem login, com aviso amarelo "Sem conexão… dados salvos em 13/11/2026 às 10:04" | Aprovado |
| O3 | Visão geral, Estoque, Bolsas, Quadro de atenção e Relatórios | exibem os dados salvos (3 bolsas) | Aprovado |
| O4 | Doadores, Cadastros e Movimentações | "Esta área precisa de internet" | Aprovado |
| O5 | Botões de cadastrar, movimentar e Contas de acesso | escondidos sem conexão | Aprovado |
| O6 | Nenhum dado pessoal no aparelho | retrato sem e-mail, telefone, CPF, endereço, nascimento, observações ou responsável | Aprovado |
| O7 | Sair | volta ao login e apaga o retrato do aparelho | Aprovado |
| O8 | Retrato com mais de 24 horas | descartado; vai para o login | Aprovado |
| O9 | Manifesto, ícones e service worker servidos corretamente | teste automatizado | Aprovado |
| O10 | Defeito encontrado: botão "Nova bolsa" aparecia sem permissão (e sem conexão) | agora só para quem pode cadastrar bolsa | Corrigido |
| O11 | Instalação do app e abertura sem internet no celular | o navegador embutido do editor não executa service workers; a confirmar no celular/Chrome | Pendente (usuário) |
| O12 | Testes automatizados | 57/57 | Aprovado |
