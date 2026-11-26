# Assistente HemoFlow (agente de IA com RAG)

**Autores:** José Kaike Gomes dos Santos e João Manoel da Silva Oliveira

O assistente tira dúvidas de doadores e parceiros sobre o HemoFlow e sobre doação de sangue. Ele usa só a base de conhecimento do projeto (o FAQ) e, quando é um doador logado, os dados do próprio cadastro, consultados apenas para leitura.

A explicação completa (como funciona, por que fizemos assim e o resultado dos testes) está em [`docs/assistente-rag.md`](../docs/assistente-rag.md). Este arquivo é o guia prático para instalar e rodar.

## Resumo de como funciona

1. `indexar.py` divide o FAQ ([`base/faq_hemoflow.txt`](base/faq_hemoflow.txt), 14 seções e 58 perguntas) em trechos e gera dois vetores para cada um.
2. `busca.py` compara a pergunta com os trechos e separa os 6 mais parecidos.
3. `agente.py` envia à IA as regras, os trechos e a pergunta. Se nada for parecido, responde que não encontrou, sem chamar a IA.
4. `ferramentas.py` deixa a IA consultar o banco, só para leitura e só os dados de quem está logado.
5. A resposta sempre termina com a fonte.

## Instalação no computador (Windows, PowerShell, dentro da pasta `assistente`)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
copy .env.example .env
```

Depois de copiar, abra o `.env` e coloque a sua chave em `OPENAI_API_KEY`. Em seguida:

```powershell
python scripts\criar_usuario_leitura.py
python scripts\verificar_ambiente.py
python indexar.py
```

O primeiro comando cria no MySQL o usuário `hemoflow_leitura`, que só pode ler (pede a senha do root). O segundo confere se está tudo pronto e deve terminar com "Ambiente OK". O terceiro monta o índice; na primeira vez ele baixa o modelo de embeddings, de uns 470 MB.

## Como usar

| Comando | Para que serve |
|---|---|
| `python chat_terminal.py` | conversa pelo terminal, só com o FAQ |
| `python chat_terminal.py --doador doador@exemplo.com` | simula um doador logado, para testar as ferramentas |
| `python chat_terminal.py --sem-ia` | mostra só os trechos encontrados, sem gastar crédito |
| `python testes\rodar_testes.py --doador doador@exemplo.com` | roda as 15 perguntas de teste e grava `testes\relatorio.md` |

Para trocar de provedor de IA (Gemini, Ollama), basta mudar `LLM_BASE_URL` e `LLM_MODELO` no `.env`.

## O assistente dentro do app, no computador

1. Na pasta do projeto, ligue o HemoFlow com `python scripts\dev.py`.
2. Em outro terminal, na pasta `assistente`, rode `.venv\Scripts\Activate.ps1` e depois `python servico.py`. Espere aparecer "Assistente HemoFlow pronto".
3. No app do doador aparece o botão 💬 no topo e o item Perfil › Assistente HemoFlow. No painel do parceiro aparece o item Assistente, que responde só pelo FAQ.

O `servico.py` só aceita conexões do próprio computador e exige o segredo `ASSISTENTE_SEGREDO` do `.env`. Se ele estiver desligado, o botão não aparece e o resto do app continua normal.

## O assistente no site publicado (Railway)

Na nuvem não existe o `servico.py`: o agente roda dentro do próprio servidor do HemoFlow, e os vetores vêm da API da OpenAI (`text-embedding-3-small`). Assim a imagem não precisa levar o PyTorch nem o modelo local. O Dockerfile já copia os arquivos do agente e o FAQ e já define `ASSISTENTE_EMBEDDINGS=openai`.

Para ligar, basta criar a variável `OPENAI_API_KEY` no serviço hemoflow do Railway. O limiar de "fora do assunto" na nuvem é 0,40, medido com perguntas reais.

Limites de gasto, que valem nos dois modos:

- 15 perguntas a cada 10 minutos por pessoa;
- 100 perguntas por dia no total (variável `HEMOFLOW_ASSISTENTE_LIMITE_DIA`).

## Testes

| Relatório | Conteúdo |
|---|---|
| [`testes/relatorio.md`](testes/relatorio.md) | versão final no computador: 15 de 15 respostas corretas, com a fonte certa |
| [`testes/relatorio_nuvem.md`](testes/relatorio_nuvem.md) | modo nuvem testado pelo app: 15 de 15 corretas, parceiro respondido e limite diário funcionando |
| [`testes/relatorio_busca.md`](testes/relatorio_busca.md) | primeira rodada, só da busca (antes dos ajustes) |

## O que não vai para o GitHub

O `.env` (chave da IA e senha do banco), a pasta `.venv` e o índice gerado (`indice/`) ficam só no computador.
