# Assistente HemoFlow — mini agente de IA com RAG

Agente que tira dúvidas de doadores e parceiros sobre o HemoFlow e sobre doação de sangue, usando **somente** a base de conhecimento do projeto (FAQ) e, para o doador logado, **dados do próprio cadastro** consultados em modo somente leitura.

## Como funciona (RAG)

```
pergunta ──► busca.py ──► 6 trechos mais parecidos do FAQ ──► agente.py ──► IA (OpenAI) ──► resposta + "Fonte:"
                 ▲          (embeddings locais, cosseno)            │
          indexar.py                                                ▼
   base/faq_hemoflow.txt                        ferramentas.py (SÓ LEITURA no MySQL do HemoFlow)
```

1. **Base de conhecimento:** [`base/faq_hemoflow.txt`](base/faq_hemoflow.txt) (13 seções, 52 perguntas; versão em PDF ao lado), no formato do exemplo da disciplina.
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

## Resultado dos testes

[`testes/relatorio.md`](testes/relatorio.md): 15 perguntas (FAQ, dados do doador, saúde e fora do escopo), com os trechos recuperados, a resposta e a fonte. Na versão final, as 15 respostas estão corretas e citam a fonte certa.

Projeto HemoFlow — José Kaike Gomes dos Santos e João Manoel da Silva Oliveira · ADS UNINASSAU Caruaru.
