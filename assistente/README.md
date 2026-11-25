# Assistente HemoFlow — mini agente de IA com RAG

Agente que tira dúvidas de doadores e parceiros sobre o HemoFlow e sobre doação de sangue, usando **somente** a base de conhecimento do projeto (FAQ) e, para o doador logado, **dados do próprio cadastro** consultados em modo somente leitura.

## Como funciona (RAG)

```
pergunta ──► busca.py ──► 6 trechos mais parecidos do FAQ ──► agente.py ──► IA (OpenAI) ──► resposta + "Fonte:"
                 ▲          (embeddings locais, cosseno)            │
          indexar.py                                                ▼
   base/faq_hemoflow.txt                        ferramentas.py (SÓ LEITURA no MySQL do HemoFlow)
```

1. **Base de conhecimento:** [`base/faq_hemoflow.txt`](base/faq_hemoflow.txt) (14 seções, 58 perguntas, incluindo uma seção para parceiros; versão em PDF ao lado), no formato do exemplo da disciplina.
2. **Indexação (`indexar.py`):** um trecho por pergunta + resposta, com o título da seção. Dois embeddings por trecho (só a pergunta e o trecho inteiro) com o modelo local `paraphrase-multilingual-MiniLM-L12-v2` (~470 MB, baixado na 1ª vez).
3. **Busca (`busca.py`):** semelhança de cosseno; nota = média das duas comparações. Medido nos testes: o trecho certo fica entre os 6 primeiros em 10 de 11 perguntas.
4. **Resposta (`agente.py`):** a IA recebe as regras (prompt de sistema), os 6 trechos e a pergunta. Se nem o melhor trecho for minimamente parecido, responde "não sei" sem chamar a IA.
5. **Ferramentas (`ferramentas.py`, padrão da Aula 7):** `quando_posso_doar`, `minha_meta_isencao`, `meus_cupons_e_convocacoes` (só do doador logado), `nivel_do_estoque` e `locais_de_doacao`.

### Regras do agente
Português, curto e claro · só os trechos recuperados e as ferramentas · se não estiver na base, diz que não sabe e indica o banco de sangue, o HEMOPE ou a aba Ajuda · nada de orientação médica (manda para a triagem) · não inventa números, endereços, horários ou estoque · termina com a **Fonte** (seção do FAQ ou dado consultado).

### Segurança e privacidade
- O id do doador **não é um parâmetro da IA**: vem da sessão e fica preso às ferramentas. A IA não consegue consultar outra pessoa.
- Usuário do MySQL `hemoflow_leitura` **só com SELECT** em 14 tabelas (criado por `scripts/criar_usuario_leitura.py`); a conexão ainda abre em modo READ ONLY. Testado: tentativa de escrita é recusada (erro 1142).
- As ferramentas não devolvem CPF, e-mail, telefone nem quantidade de bolsas.
- O `.env` (chave da IA e senha do banco), o `.venv` e o índice não vão para o GitHub.

## Instalação (Windows, PowerShell, dentro de `assistente/`)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
copy .env.example .env                 # depois coloque a chave em OPENAI_API_KEY
python scripts\criar_usuario_leitura.py  # usuário só leitura no MySQL (pede a senha do root)
python scripts\verificar_ambiente.py     # deve terminar em "Ambiente OK — pronto para começar!"
python indexar.py
```

## Uso

```powershell
python chat_terminal.py                               # conversa só com o FAQ
python chat_terminal.py --doador doador@exemplo.com   # simula o doador logado (testa as ferramentas)
python chat_terminal.py --sem-ia                      # só mostra os trechos encontrados (não gasta crédito)
python testes\rodar_testes.py --doador doador@exemplo.com   # 15 perguntas -> testes\relatorio.md
```

Trocar de provedor de IA (Gemini, Ollama) é só mudar `LLM_BASE_URL` e `LLM_MODELO` no `.env`.

## Aba "Assistente" dentro do app

1. Ligue o HemoFlow (`python scripts\dev.py`, na pasta do projeto).
2. Em outro terminal, na pasta `assistente`: `.venv\Scripts\Activate.ps1` e `python servico.py` (espera aparecer “Assistente HemoFlow pronto…”).
3. No app do doador aparece o botão 💬 no topo e o item **Perfil › Assistente HemoFlow**; no painel do parceiro, o item **Assistente** (só FAQ, sem dados de doador).

Como funciona: o HemoFlow (`POST /api/doador/assistente` ou `/api/parceiro/assistente`) repassa a pergunta e o id do doador logado para o `servico.py`, que só aceita conexões do próprio computador e exige o `ASSISTENTE_SEGREDO` do `.env`. Limite de 15 perguntas a cada 10 minutos por pessoa (controle de gasto). A conversa não é salva. Onde o serviço não está ligado (por exemplo, na nuvem), o botão simplesmente não aparece.

## Na nuvem (Railway)

No site publicado o assistente roda **dentro do próprio servidor do HemoFlow**, sem o `servico.py` e sem PyTorch:

- A imagem (Dockerfile) já leva `config.py`, `busca.py`, `agente.py`, `ferramentas.py`, `indexar.py` e o FAQ, e já define `ASSISTENTE_EMBEDDINGS=openai`.
- Os embeddings vêm da API da OpenAI (`text-embedding-3-small`). O índice do FAQ (58 trechos, 2 vetores cada) é montado na primeira pergunta e fica na memória.
- O limiar muda com o modelo: **0,40** na nuvem. Medido: perguntas do HemoFlow ≥ 0,47 e fora do assunto ≤ 0,39.
- As ferramentas usam a conexão do próprio HemoFlow (com TLS), sempre em transação `READ ONLY`.
- **Para ligar:** crie a variável `OPENAI_API_KEY` no serviço hemoflow do Railway (a mesma chave do `.env`). Sem ela, a aba some.
- **Limites de gasto:** 15 perguntas a cada 10 minutos por pessoa e **100 perguntas por dia** no total (`HEMOFLOW_ASSISTENTE_LIMITE_DIA`). A conta do dia usa a auditoria (`PERGUNTA_IA`), que guarda só que houve uma pergunta, nunca o texto.
- Teste do modo nuvem pelo app (banco temporário com dados fictícios): [`testes/relatorio_nuvem.md`](testes/relatorio_nuvem.md). As 15 perguntas responderam certo, o parceiro também, e a 18ª pergunta com limite 17 foi recusada (429).

No computador nada muda: continua o modelo local da disciplina (`sentence-transformers`) com o `servico.py`.

## Resultado dos testes

[`testes/relatorio.md`](testes/relatorio.md): 15 perguntas (FAQ, dados do doador, saúde e fora do escopo), com os trechos recuperados, a resposta e a fonte. Na versão final, as 15 respostas estão corretas e citam a fonte certa.

Projeto HemoFlow — José Kaike Gomes dos Santos e João Manoel da Silva Oliveira · ADS UNINASSAU Caruaru.
