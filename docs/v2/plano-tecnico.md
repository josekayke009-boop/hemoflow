# Plano técnico da versão 2.0

**Autores:** José Kaike Gomes dos Santos e João Manoel da Silva Oliveira. Concepção da versão 2.0: João Manoel da Silva Oliveira.

Este é o plano que escrevemos antes de construir a versão 2.0. A versão 2.1 veio depois e está descrita na [documentação completa](../documentacao/HemoFlow%20-%20Documentacao%202.1.pdf).

Plataforma de captação e fidelização de doadores para **bancos de sangue privados** (Brasil, piloto em PE).
Mesma tecnologia da versão 1: Python (`http.server`) + MySQL 8 + HTML/CSS/JS + PWA, publicada no Railway.
Um único sistema, um servidor e um banco de dados: app do doador, painel do banco, painel do parceiro e admin.

## Perfis de acesso

| Perfil | Quem é | Vê |
|---|---|---|
| `ADMINISTRADOR` | Equipe HemoFlow | Tudo, com edição; cada ação vai para `historico_auditoria` |
| `BANCO` | Equipe de captação de um banco privado (`usuarios.banco_id`) | Termômetro, estoque, convocações, agenda, confirmação, métricas do próprio banco |
| `PARCEIRO` | Comércio, cursinho, pré-Enem, faculdade (`usuarios.parceiro_id`) | Ofertas, validação de cupons, código e relatório agregado |
| `DOADOR` | Doador (`doadores.usuario_id`) | App: termômetro (cores), aptidão, agendamento, histórico, direitos, vantagens, grupos |

## Banco de dados (migração 005, só acrescenta)

- `bancos_sangue`, `unidades` (unidade de banco parceiro ou local público, como o HEMOPE)
- `estoque_niveis` (quantidade e limites por unidade e tipo) e `estoque_movimentos` (entradas e saídas)
- `doadores` + colunas: `usuario_id`, `sexo`, `ultima_doacao_informada`, consentimentos, responsável (menores)
- `vagas`, `convocacoes`, `convocacao_doadores`, `agenda_doacoes` (com código do balcão), `historico_doacoes`
- `parceiros`, `doador_parceiros`, `ofertas`, `cupons`, `grupos`, `grupo_membros`
- `beneficios_estado`, `avisos`, `codigos_login`
- `usuarios` + colunas `banco_id`, `parceiro_id`; novos perfis `BANCO`, `PARCEIRO`, `DOADOR`

A ideia era remover depois as tabelas da versão 1 (bolsas, movimentações de bolsa, reservas, descartes, locais de armazenamento e profissionais). Acabamos mantendo essas tabelas no banco, sem uso, porque a migração 006 foi usada para os recursos da versão 2.1.

## Regras (arquivo `regras.py`, coberto por testes)

- Compatibilidade de hemácias (quem doa para quem).
- Aptidão: 60 dias (homens) ou 90 dias (mulheres) desde a última doação; até 4 (homens) ou 3 (mulheres) em 12 meses; 16 a 69 anos; 16 e 17 anos só com consentimento do responsável. A aptidão final é a triagem do banco.
- Termômetro: Crítico até `limite_critico`, Atenção até `limite_atencao`, Normal acima. Faltam = `limite_atencao + 1 − quantidade`.
- Convocação: compatível + apto + mesma cidade/UF + consentiu, limitada às vagas livres.
- Doação verificada só quando o banco confirma o código no balcão; a declarada pelo doador fica "declarada".
- Meta de isenção por estado (PE: 3 homens / 2 mulheres em 12 meses); folga CLT nacional.
- Cupom: doação verificada nos últimos 6 meses; uso único; validade.

## Etapas

1. Branch `v2`, plano e regras com testes.
2. Migração 005 (backup antes) no MySQL local.
3. Servidor: login por código, cadastro do doador, rotas do doador, do banco, do parceiro, do admin e avisos.
4. Telas: login 3D (mantido), app do doador (claro/escuro, acessível) e painéis web.
5. Testes, dados fictícios de demonstração, documentação.
6. Merge na `main`, publicação no Railway (backup e migração na nuvem) e QR Code.
