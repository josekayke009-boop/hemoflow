"""Assistente HemoFlow — confere se o ambiente está pronto (mesma ideia do verificador do curso).

Uso (com o .venv ativado, dentro da pasta assistente):  python scripts/verificar_ambiente.py
"""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
ok = True


def item(passou: bool, texto: str, dica: str = ""):
    global ok
    print(f"  {'✓' if passou else '✗'} {texto}" + (f"\n      → {dica}" if not passou and dica else ""))
    ok = ok and passou


print("Verificando o ambiente do Assistente HemoFlow…\n")
item(sys.version_info >= (3, 10), f"Python {sys.version.split()[0]} (precisa 3.10+)", "Instale o Python 3.10 ou mais novo.")
item(sys.prefix != sys.base_prefix, "Ambiente virtual (.venv) ativado", r"Ative:  .venv\Scripts\Activate.ps1")
for nome in ("torch", "sentence_transformers", "numpy", "openai", "dotenv", "mysql.connector"):
    try:
        m = importlib.import_module(nome)
        item(True, f"{nome} {getattr(m, '__version__', '')}".strip())
    except ImportError:
        item(False, f"{nome} não instalado", "Rode os comandos de instalação do README do assistente.")

try:
    import config
    item((config.PASTA / ".env").exists(), "Arquivo .env criado", r"copy .env.example .env  e preencha a chave")
    item(bool(config.OPENAI_API_KEY), "Chave da IA (OPENAI_API_KEY) preenchida no .env",
         "Sem a chave, a busca no FAQ funciona, mas a IA não escreve as respostas.")
    item(config.ARQUIVO_FAQ.exists(), "Base de conhecimento (base/faq_hemoflow.txt)")
    item((config.PASTA_INDICE / "vetores.npy").exists(), "Índice criado", "Rode:  python indexar.py")
    try:
        import mysql.connector
        mysql.connector.connect(**config.DB, connection_timeout=5).close()
        item(True, f"Banco do HemoFlow acessível ({config.DB['host']}/{config.DB['database']}, usuário {config.DB['user']})")
    except Exception as exc:  # noqa: BLE001
        item(False, "Banco do HemoFlow inacessível", f"Confira HEMOFLOW_DB_* no .env ({type(exc).__name__}).")
except Exception as exc:  # noqa: BLE001
    item(False, f"Erro ao ler a configuração: {exc}")

print("\nAmbiente OK — pronto para começar!" if ok else "\nHá itens com ✗ acima: siga as dicas e rode de novo.")
