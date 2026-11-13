# Roteiro de apresentação

Tempo sugerido: 10 a 15 minutos. Abra o sistema em https://hemoflow-production.up.railway.app antes de começar (ou mostre o QR Code no slide para a turma acessar pelo celular).

## 1. Problema (1 min)

Hemocentros precisam saber, a qualquer momento, quantas bolsas de cada tipo sanguíneo estão disponíveis, quais estão perto de vencer e quem são os doadores cadastrados. Planilhas e controles manuais dificultam essa visão e não registram quem fez cada alteração.

## 2. Proposta (1 min)

O HemoFlow centraliza doadores, profissionais, bolsas e movimentações num sistema web com controle de acesso por perfil, alertas automáticos e histórico de tudo o que acontece com cada bolsa.

## 3. Tecnologias e arquitetura (2 min)

- Python no servidor, MySQL no banco, HTML/CSS/JavaScript nas telas.
- Hospedado na nuvem (Railway), com HTTPS e publicação automática a partir do GitHub.
- Mostrar o diagrama de [arquitetura.md](arquitetura.md) e o diagrama do [banco de dados](banco-de-dados.md).

## 4. Demonstração (6 a 8 min)

1. **Tela de login** — fundo animado; tentar uma senha errada (mensagem de erro).
2. **"Esqueceu sua senha?"** — mostrar que o e-mail chega com o link de recuperação.
3. **Entrar como administrador** — Visão geral com os números do estoque.
4. **Cadastros → Novo doador** — preencher com dados fictícios, mostrar as máscaras de telefone/CPF/CEP e o endereço; depois tentar o **mesmo e-mail** (bloqueado).
5. **Doadores** — cidade na lista; excluir um doador de teste (janela de confirmação e aviso verde).
6. **Registro de bolsas** — registrar uma bolsa; depois **Nova movimentação** para reservar e liberar.
7. **Movimentações** — histórico com responsável e data.
8. **Sino de notificações** — estoque crítico por tipo; clicar para dar baixa.
9. **Contas de acesso** — criar uma conta com perfil **Consulta** e mostrar que esse perfil não vê os botões de cadastro.
10. **Celular** — abrir pelo QR Code, mostrar o menu inferior e a instalação como aplicativo.

## 5. Segurança e qualidade (1 min)

Senhas com hash, permissões verificadas no servidor, bloqueio após tentativas erradas, e-mail único garantido pelo banco, 57 testes automatizados e relatório de testes manuais ([relatorio-testes.md](relatorio-testes.md)).

## 6. Próximos passos (1 min)

Tela de edição de doador, agendamento de doações, relatórios exportáveis (PDF/Excel), comunicação interna entre equipes e alertas configuráveis por estoque mínimo — as tabelas para isso já existem no banco.

## Dicas

- Use somente dados fictícios na demonstração.
- Entre no sistema alguns minutos antes, para conferir que está tudo no ar.
- Tenha o computador local (`iniciar_hemoflow.ps1`) como plano B, caso a internet da sala falhe.
