"""Assistente HemoFlow — configuração (lida do arquivo .env desta pasta).

O .env é pessoal e NUNCA vai para o GitHub (está no .gitignore). Modelo em .env.example.
"""
import os
from pathlib import Path

try:  # na nuvem não há .env: tudo vem das variáveis do Railway
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

PASTA = Path(__file__).resolve().parent
if load_dotenv:
    load_dotenv(PASTA / ".env")

# Base de conhecimento e índice
ARQUIVO_FAQ = PASTA / "base" / "faq_hemoflow.txt"
PASTA_INDICE = PASTA / "indice"
MODELO_EMBEDDINGS = os.getenv("MODELO_EMBEDDINGS", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
# "local" (padrão, computador): modelo acima com sentence-transformers.
# "openai" (nuvem): embeddings pela API da OpenAI, sem PyTorch e sem o modelo de 470 MB na imagem.
EMBEDDINGS = os.getenv("ASSISTENTE_EMBEDDINGS", "local").strip().lower()
MODELO_EMBEDDINGS_NUVEM = os.getenv("MODELO_EMBEDDINGS_NUVEM", "text-embedding-3-small")
TOP_K = int(os.getenv("TOP_K", "6"))                         # quantos trechos do FAQ vão para a IA
# Se nem o melhor trecho chega a essa nota, a pergunta está fora do assunto: responde "não sei" sem chamar a IA.
# Acima dela, quem decide se os trechos respondem é a IA, seguindo o prompt (regra 3).
# Cada modelo de embeddings tem a sua escala de notas, por isso o limiar padrão muda com ele.
LIMIAR_SEMELHANCA = float(os.getenv("LIMIAR_SEMELHANCA", "0.25" if EMBEDDINGS == "local" else "0.40"))  # medido: perguntas do HemoFlow ≥ 0,47; fora do assunto ≤ 0,39

# LLM (OpenAI por padrão). Para outro provedor compatível, mude só LLM_BASE_URL e LLM_MODELO:
#   Gemini: LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/  LLM_MODELO=gemini-2.0-flash
#   Ollama: LLM_BASE_URL=http://localhost:11434/v1  LLM_MODELO=llama3.2  (chave pode ser qualquer texto)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").strip() or None
LLM_MODELO = os.getenv("LLM_MODELO", "gpt-4o-mini")

# Banco do projeto (padrão da Aula 7): use um usuário do MySQL SÓ DE LEITURA.
DB = {
    "host": os.getenv("HEMOFLOW_DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("HEMOFLOW_DB_PORT", "3306")),
    "database": os.getenv("HEMOFLOW_DB_NAME", "hemoflow"),
    "user": os.getenv("HEMOFLOW_DB_USER", "hemoflow_leitura"),
    "password": os.getenv("HEMOFLOW_DB_PASSWORD", ""),
}

# Serviço local que o HemoFlow chama (aba Assistente). O segredo impede que outro programa use o serviço.
SERVICO_PORTA = int(os.getenv("ASSISTENTE_PORTA", "8765"))
SERVICO_SEGREDO = os.getenv("ASSISTENTE_SEGREDO", "").strip()
