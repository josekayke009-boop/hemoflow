"""Assistente HemoFlow — roda as 15 perguntas de teste e grava testes/relatorio.md.

Uso (pasta assistente, .venv ativado):
  python testes/rodar_testes.py --doador doador@exemplo.com   com a IA (precisa da chave no .env)
  python testes/rodar_testes.py --sem-ia                       só a busca no FAQ (não gasta crédito)
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

PASTA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA.parent))
import busca  # noqa: E402
import config  # noqa: E402
from agente import Assistente  # noqa: E402
from chat_terminal import doador_por_email  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--doador", default="doador@exemplo.com")
    p.add_argument("--sem-ia", action="store_true")
    a = p.parse_args()
    perguntas = json.loads((PASTA / "perguntas.json").read_text(encoding="utf-8"))
    doador_id = None if a.sem_ia else doador_por_email(a.doador)
    com_doador, sem_doador = Assistente(doador_id), Assistente(None)
    linhas = ["# Assistente HemoFlow — relatório dos testes\n",
              f"Gerado em {datetime.now():%d/%m/%Y %H:%M} · modelo de embeddings `{config.MODELO_EMBEDDINGS}` · "
              f"top-k {config.TOP_K} · limiar {config.LIMIAR_SEMELHANCA}" +
              ("" if a.sem_ia else f" · IA `{config.LLM_MODELO}` · doador de teste: {a.doador if doador_id else 'não encontrado'}") + "\n"]
    for q in perguntas:
        print(f"[{q['n']:2}] {q['pergunta']}")
        linhas.append(f"\n## {q['n']}. {q['pergunta']}\n\n*Esperado:* {q['esperado']}\n")
        trechos = busca.buscar(q["pergunta"])
        linhas.append("*Trechos recuperados:* " + "; ".join(f"{t['secao']} — “{t['pergunta']}” ({t['semelhanca']:.2f})" for t in trechos[:3]) + "\n")
        if a.sem_ia:
            continue
        inicio = time.time()
        r = (com_doador if q.get("doador") else sem_doador).responder(q["pergunta"])
        linhas.append(f"\n**Resposta do agente** ({time.time() - inicio:.1f} s"
                      + (f", ferramentas: {', '.join(r['ferramentas'])}" if r["ferramentas"] else "") + "):\n\n> "
                      + r["resposta"].replace("\n", "\n> ") + "\n")
    destino = PASTA / ("relatorio_busca.md" if a.sem_ia else "relatorio.md")
    destino.write_text("\n".join(linhas), encoding="utf-8")
    print(f"\nRelatório salvo em {destino}")


if __name__ == "__main__":
    main()
