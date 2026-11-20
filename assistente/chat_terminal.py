"""Assistente HemoFlow — conversa pelo terminal.

Uso:
  python chat_terminal.py                          só o FAQ (sem dados pessoais)
  python chat_terminal.py --doador doador@exemplo.com   simula o doador logado (para testar as ferramentas)
  python chat_terminal.py --sem-ia                 mostra só os trechos encontrados (não usa a chave da IA)
Digite "sair" para terminar.
"""
import argparse

import busca
from agente import Assistente
from ferramentas import Ferramentas


def doador_por_email(email: str) -> int | None:
    r = Ferramentas()._consulta("SELECT d.id FROM doadores d JOIN usuarios u ON u.id=d.usuario_id WHERE u.email=%s", (email,), um=True)
    return r["id"] if r else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--doador", help="e-mail de um doador para testar as ferramentas (só no computador)")
    p.add_argument("--sem-ia", action="store_true", help="mostra só a busca no FAQ")
    a = p.parse_args()
    doador_id = doador_por_email(a.doador) if a.doador else None
    if a.doador and not doador_id:
        print("Doador não encontrado; seguindo só com o FAQ.")
    print("Assistente HemoFlow — carregando…")
    busca.carregar()
    assistente = Assistente(doador_id)
    print("Pronto! Pergunte sobre doação de sangue ou sobre o HemoFlow (\"sair\" para terminar).\n")
    while True:
        try:
            pergunta = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if pergunta.lower() in ("sair", "exit", "quit"):
            break
        if not pergunta:
            continue
        if a.sem_ia:
            for t in busca.buscar(pergunta):
                print(f"  {t['semelhanca']:.2f}  [{t['secao']}] {t['pergunta']}")
            continue
        try:
            r = assistente.responder(pergunta)
        except Exception as exc:  # noqa: BLE001 - mostra o erro de forma amigável no terminal
            print(f"Assistente: (erro) {exc}\n")
            continue
        print(f"Assistente: {r['resposta']}")
        if r["ferramentas"]:
            print(f"  (consultou: {', '.join(r['ferramentas'])})")
        print()


if __name__ == "__main__":
    main()
